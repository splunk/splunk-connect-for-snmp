# SC4SNMP Helm installation

The basic installation and configuration process discussed in this section is typical 
for single node non-HA deployments. It does not have resource requests and limits.
See the mongo, redis, scheduler, worker, and traps configuration sections for guidance
on production configuration.

## Installation process

### Online installation

#### Add SC4SNMP repository
```
microk8s helm3 repo add splunk-connect-for-snmp https://splunk.github.io/splunk-connect-for-snmp
microk8s helm3 repo update
```
Now the package should be visible in `helm3` search command result:
``` bash
microk8s helm3 search repo snmp
```
Example output:
``` 
NAME                                               CHART VERSION  APP VERSION    DESCRIPTION                           
splunk-connect-for-snmp/splunk-connect-for-snmp        1.0.0        1.0.0       A Helm chart for SNMP Connect for SNMP
```

#### Download and modify values.yaml

The installation of SC4SNMP requires the creation of a `values.yaml` file, which serves as the configuration file. To configure this file, follow these steps:

1. Start with checking out the [basic configuration template][basic_template_link]
2. Review the [examples][examples_link] to determine which areas require configuration.
3. For more advanced configuration options, refer to the complete default [values.yaml](https://github.com/splunk/splunk-connect-for-snmp/blob/main/charts/splunk-connect-for-snmp/values.yaml)
or download it directly from Helm using the command `microk8s helm3 show values splunk-connect-for-snmp/splunk-connect-for-snmp` 
4. In order to learn more about each of the config parts, check [configuration](../configuration/deployment-configuration.md) section.

It is recommended to start by completing the base template and gradually add additional configurations as needed.

#### Install SC4SNMP

After the `values.yaml` creation, you can proceed with the SC4SNMP installation:

``` bash
microk8s helm3 install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
```

From now on, when editing SC4SNMP configuration, the configuration change must be
inserted in the corresponding section of `values.yaml`. For more details check [configuration](../configuration/deployment-configuration.md) section.

Use the following command to propagate configuration changes:
``` bash
microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
```

### Offline installation

For offline installation instructions see [this page](../offlineinstallation/offline-sc4snmp.md).

## Verification of the deployment

In a few minutes, all pods should be up and running. It can be verified with:

``` bash
microk8s kubectl get pods -n sc4snmp
```

Example output:

``` 
NAME                                                      READY   STATUS             RESTARTS      AGE
snmp-splunk-connect-for-snmp-scheduler-7ddbc8d75-bljsj        1/1     Running   0          133m
snmp-splunk-connect-for-snmp-worker-poller-57cd8f4665-9z9vx   1/1     Running   0          133m
snmp-splunk-connect-for-snmp-worker-sender-5c44cbb9c5-ppmb5   1/1     Running   0          133m
snmp-splunk-connect-for-snmp-worker-trap-549766d4-28qzh       1/1     Running   0          133m
snmp-mibserver-7f879c5b7c-hz9tz                               1/1     Running   0          133m
snmp-mongodb-869cc8586f-vvr9f                                 2/2     Running   0          133m
snmp-redis-master-0                                           1/1     Running   0          133m
snmp-splunk-connect-for-snmp-trap-78759bfc8b-79m6d            1/1     Running   0          99m
snmp-splunk-connect-for-snmp-inventory-mjccw                  0/1     Completed 0          6s
```

The output may differ depending on the config. The example from the above have both polling and traps configured,
and the data is being sent to Splunk.

If you have `traps` configured, you should see `EXTERNAL-IP` in `snmp-splunk-connect-for-snmp-trap` service.
Check it using the command:

```bash
microk8s kubectl get svc -n sc4snmp 
```

An example the correct setup is:

```
NAME                                TYPE           CLUSTER-IP       EXTERNAL-IP   PORT(S)         AGE
snmp-redis-headless                 ClusterIP      None             <none>        6379/TCP        33h
snmp-mongodb                        ClusterIP      10.152.183.147   <none>        27017/TCP       33h
snmp-mibserver                      ClusterIP      10.152.183.253   <none>        80/TCP          33h
snmp-redis-master                   ClusterIP      10.152.183.135   <none>        6379/TCP        33h
snmp-mongodb-metrics                ClusterIP      10.152.183.217   <none>        9216/TCP        33h
snmp-splunk-connect-for-snmp-trap   LoadBalancer   10.152.183.33    10.202.9.21   162:30161/UDP   33h
```

If there's `<pending>` communicate instead of the IP address, that means you either provided the wrong IP address
in `traps.loadBalancerIP` or there's something wrong with the `metallb` microk8s addon.

For the sake of the example, let's assume we haven't changed the default indexes names and the metric data goes to `netmetrics`
and the events goes to `netops`.

#### Test SNMP Traps

1. Simulate the event. On a Linux system, you can download `snmpd` package for its purpose and run:

``` bash
apt update
apt-get install snmpd
snmptrap -v2c -c public EXTERNAL-IP 123 1.3.6.1.2.1.1.4 1.3.6.1.2.1.1.4 s test
```

Remember to replace `EXTERNAL-IP` with the ip address of the `snmp-splunk-connect-for-snmp-trap` service from the above.

2. Search Splunk: You should see one event per trap command with the host value of the test machine `EXTERNAL-IP` IP address.

``` bash
index="netops" sourcetype="sc4snmp:traps"
```

#### Test SNMP Poller

1. To test SNMP poller, you can either use the device you already have, or configure snmpd on your Linux system. 
Snmpd needs to be configured to listen on the external IP. To enable listening snmpd to external IP, go to the `/etc/snmp/snmpd.conf` configuration file, and replace the IP address `10.0.101.22` with the server IP address where snmpd is configured.
`agentaddress  10.0.101.22,127.0.0.1,[::1]`. Restart snmpd through the execute command:

``` bash
service snmpd stop
service snmpd start
```

2. Configure SC4SNMP Poller to test and add the IP address which you want to poll. Add the configuration entry into the `values.yaml` file by 
replacing the IP address `10.0.101.22` with the server IP address where the snmpd was configured.
``` bash
poller:
  inventory: |
    address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
    10.0.101.22,,2c,public,,,42000,,,
```

3. Load `values.yaml` file into SC4SNMP

``` bash
microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
```

4. Verify if the records appeared in Splunk:

``` bash
index="netops" sourcetype="sc4snmp:event"
```

``` bash
| mpreview index="netmetrics" | search sourcetype="sc4snmp:metric"
```

NOTE: Before polling starts, SC4SNMP must perform SNMP WALK process on the device. It is run first time after configuring the new device, and then the run time in every `walk_interval`. 
Its purpose is to gather all the data and provide meaningful context for the polling records. For example, it might report that your device is so large that the walk takes too long, so the scope of walking needs to be limited.
In such cases, enable the small walk. See: [walk takes too much time](../../bestpractices/#walking-a-device-takes-too-much-time).
When the walk finishes, events appear in Splunk. Confirm the walk with the following queries:



[examples_link]: https://github.com/splunk/splunk-connect-for-snmp/tree/main/examples
[basic_template_link]: https://github.com/splunk/splunk-connect-for-snmp/blob/main/examples/basic_template.md