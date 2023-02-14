# SC4SNMP Helm installation

The basic installation and configuration process discussed in this section is typical 
for single node non-HA deployments. It does not have resource requests and limits.
See the mongo, redis, scheduler, worker, and traps configuration sections for guidance
on production configuration.

### Offline installation

For offline installation instructions see [this page](../offlineinstallation/offline-sc4snmp.md).

### Add SC4SNMP repository
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

### Download and modify values.yaml

SC4SNMP installation requires creating `values.yaml` file, where you can specify its configuration.
Check the default `values.yaml` with all parameters described using the command:

```bash
microk8s helm3 show values splunk-connect-for-snmp/splunk-connect-for-snmp 
```

or view them directly on GitHub: [values.yaml](https://github.com/splunk/splunk-connect-for-snmp/blob/main/charts/splunk-connect-for-snmp/values.yaml).

To successfully run SC4SNMP you need to at least configure `splunk` or/and `sim` section - depending on where you want 
to send the data and traps or polling sections that are described here: [basic values.yaml template](https://github.com/splunk/splunk-connect-for-snmp/tree/main/examples/basic_template.md),

Here you can find the examples of the certain use-cases: [EXAMPLES](https://github.com/splunk/splunk-connect-for-snmp/tree/main/examples).

To explore all the possible configuration parameters check [configuration section](../configuration).

### Install SC4SNMP
After you create `values.yaml` of your choice, you can proceed with the SC4SNMP installation:

``` bash
microk8s helm3 install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
```

From now on, when editing SC4SNMP configuration, the configuration change must be
inserted in the corresponding section of `values.yaml`. For more details check [configuration](../configuration/deployment-configuration.md) section.

Use the following command to propagate configuration changes:
``` bash
microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
```

### Verify deployment
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

### Test SNMP Traps
- Test the Trap by logging into Splunk and confirming the presence of events
    in snmp `netops` index.

-   Test the trap from a Linux system with SNMP installed. Replace the IP address 
    `10.0.101.22` with the shared IP address above.

``` bash
apt update
apt-get install snmpd
snmptrap -v2c -c public 10.0.101.22 123 1.3.6.1.2.1.1.4 1.3.6.1.2.1.1.4 s test
```

-   Search Splunk: You should see one event per trap command with the host value of the
    test machine IP address.

``` bash
index="netops" sourcetype="sc4snmp:traps"
```

### Test SNMP Poller
- Test the Poller by logging into Splunk and confirming the presence of events
    in snmp `netops` and metrics in `netmetrics` index.

- Test the trap from a Linux system install snmpd.
    
``` bash
apt update
apt-get install snmpd
```

- To test SNMP poller, snmpd needs to be configured to listen on the external IP. To enable listening snmpd to external IP, go to the `/etc/snmp/snmpd.conf` configuration file, and replace the IP address `10.0.101.22` with the server IP address where snmpd is configured.
`agentaddress  10.0.101.22,127.0.0.1,[::1]`. Restart snmpd through the execute command:
``` bash
service snmpd stop
service snmpd start
```

- Configure SC4SNMP Poller to test and add the IP address which you want to poll. Add the configuration entry into the `values.yaml` file by 
replacing the IP address `10.0.101.22` with the server IP address where the snmpd was configured.
``` bash
poller:
  inventory: |
    address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
    10.0.101.22,,2c,public,,,42000,,,
```

- Load `values.yaml` file into SC4SNMP

``` bash
microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
```

-   Check-in Splunk
 
Before polling starts, SC4SNMP must perform SNMP WALK process on the device. It is the run first time after configuring the new device, and then the run time in every `walk_interval`. 
Its purpose is to gather all the data and provide meaningful context for the polling records. For example, it might report that your device is so large that the walk takes too long, so the scope of walking needs to be limited.
In such cases, enable the small walk. See: [walk takes too much time](../../bestpractices/#walking-a-device-takes-too-much-time).
When the walk finishes, events appear in Splunk. Confirm the walk with the following queries:

``` bash
index="netops" sourcetype="sc4snmp:event"
```

``` bash
| mpreview index="netmetrics" | search sourcetype="sc4snmp:metric"
```
