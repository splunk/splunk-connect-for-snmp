# Debug Splunk Connect for SNMP

## Check when SNMP WALK was executed last time for the device
1. [Configure Splunk OpenTelemetry Collector for Kubernetes](gettingstarted/sck-installation.md)
2. Go to your Splunk and execute search: `index="em_logs"   "Sending due task" "sc4snmp;<IP_ADDRESS>;walk"` 
and replace <IP_ADDRESS> with the pertinent IP Address. 

## Installing Splunk Connect for SNMP on Linux RedHat 
Installation of RedHat may be blocking ports required by microk8s. Installing microk8s on RedHat 
requires checking to see if the firewall is not blocking any of the [required microk8s ports](https://microk8s.io/docs/ports). 

### Accessing SC4SNMP logs 

SC4SNMP logs can be browsed in Splunk in `em_logs` index, provided that [sck-otel](gettingstarted/sck-installation.md)
is installed. Logs can be also accessed directly in kubernetes using terminal.

#### Accessing logs via Splunk
If [sck-otel](gettingstarted/sck-installation.md) is installed, browse `em_logs` index. Logs can be further filtered 
for example by the sourcetype field. Example search command to get logs from poller:
```
index=em_logs sourcetype="kube:container:splunk-connect-for-snmp-worker-poller"
```

#### Accessing logs in kubernetes
To access logs directly in kubernetes, first run `microk8s kubectl -n sc4snmp get pods`. This will output all pods:
```
NAME                                                          READY   STATUS    RESTARTS   AGE
snmp-splunk-connect-for-snmp-worker-trap-99f49c557-j9jwx      1/1     Running   0          29m
snmp-splunk-connect-for-snmp-trap-56f75f9754-kmlgb            1/1     Running   0          29m
snmp-splunk-connect-for-snmp-scheduler-7bb8c79855-rgjkj       1/1     Running   0          29m
snmp-mibserver-784bd599fd-6xzfj                               1/1     Running   0          29m
snmp-splunk-connect-for-snmp-worker-poller-78b46d668f-59mv4   1/1     Running   0          29m
snmp-splunk-connect-for-snmp-worker-sender-6f8496bfbf-cvt9l   1/1     Running   0          29m
snmp-mongodb-7579dc7867-mlnst                                 2/2     Running   0          29m
snmp-redis-master-0                                           1/1     Running   0          29m
```

Now select the desired pod and run `microk8s kubectl -n sc4snmp logs pod/<pod-name>` command. Example command to retrieve
logs from `splunk-connect-for-snmp-worker-poller`:
```
microk8s kubectl -n sc4snmp logs pod/snmp-splunk-connect-for-snmp-worker-poller-78b46d668f-59mv4
```

## Issues

### "Empty SNMP response message" problem
If you see the following line in the worker's logs:

```log
[2022-01-04 11:44:22,553: INFO/ForkPoolWorker-1] Task splunk_connect_for_snmp.snmp.tasks.walk[8e62fc62-569c-473f-a765-ff92577774e5] retry: Retry in 3489s: SnmpActionError('An error of SNMP isWalk=True for a host 192.168.10.20 occurred: Empty SNMP response message')
```
that causes an infinite retry of the walk operation. Add `worker.ignoreEmptyVarbinds` parameter to `values.yaml` and set it to true.

An example configuration for a worker in `values.yaml` is:

```yaml
worker:
  ignoreEmptyVarbinds: true
```

### "OID not increasing" problem
In case you see the following line in worker's logs:

```log
[2022-01-04 11:44:22,553: INFO/ForkPoolWorker-1] Task splunk_connect_for_snmp.snmp.tasks.walk[8e62fc62-569c-473f-a765-ff92577774e5] retry: Retry in 3489s: SnmpActionError('An error of SNMP isWalk=True for a host 192.168.10.20 occurred: OID not increasing')
```
that causes infinite retry of walk operation, add `worker.ignoreNotIncreasingOid` array to `values.yaml` and fill with the addresses of hosts where the problem appears.

An example configuration for a worker in `values.yaml` is:

```yaml
worker:
  ignoreNotIncreasingOid:
    - "127.0.0.1:164"
    - "127.0.0.6"
```

If you put in only the IP address (for example, `127.0.0.1`), then errors will be ignored for all of its devices (like `127.0.0.1:161`, 
`127.0.0.1:163`...). If you put the IP address and host as `{host}:{port}`, that means the error will be ignored only for this device.

### Walking a device takes too much time

See [Configure small walk profile](../configuration/configuring-profiles/#walk-profile) to enable the small walk functionality.

### An error of SNMP isWalk=True blocks traffic on the SC4SNMP instance

If you see many `An error of SNMP isWalk=True` errors in your logs, that means that there is a connection problem with the hosts you're polling from.
Walk will retry multiple times, which will eventually cause a worker to be blocked while it retries. In that case, you might want to limit
the maximum retry time. You can do this by setting the variable `worker.walkRetryMaxInterval`, for example:

```yaml
worker:
  walkRetryMaxInterval: 60
```

With the previous configuration, 'walk' will retry exponentially from 30 seconds until it reaches 60 seconds. The default value for `worker.walkRetryMaxInterval` is 180.

### SNMP Rollover
The Rollover problem is due to a finite stored integer value (especially when the value is 32-bit). 
When it reaches its maximum, it gets rolled down to 0 again. This causes a strange drop in Analytics data.
The most common case of this issue is interface speed on high speed ports. As a solution to this problem, SNMPv2 SMI defined a new object type, counter64, for 64-bit counters, see https://www.cisco.com/c/en/us/support/docs/ip/simple-network-management-protocol-snmp/26007-faq-snmpcounter.html.
Not all the devices support it, but if they do, poll the counter64 type OID instead of the counter32 one. 
For example, use `ifHCInOctets` instead of `ifInOctets`.

If 64-bit counter is not supported on your device, you can write your own Splunk queries that calculate the shift based on
the maximum integer value and the current state. The same works for values large enough that they don't fit into a 64-bit value.
An example for an appropriate Splunk query would be the following:


### Unknown USM user
In case of polling SNMPv3 devices, `Unknown USM user` error suggests wrong username. Verify 
that the kubernetes secret with the correct username has been created ([SNMPv3 configuration](configuration/snmpv3-configuration.md)).

### Wrong SNMP PDU digest
In case of polling SNMPv3 devices, `Wrong SNMP PDU digest` error suggests wrong authentication key. Verify 
that the kubernetes secret with the correct authentication key has been created ([SNMPv3 configuration](configuration/snmpv3-configuration.md)).

### No SNMP response received before timeout
`No SNMP response received before timeout` error might have several root causes. Some of them are:
- wrong device IP or port
- SNMPv2c wrong community string
- SNMPv3 wrong privacy key

```
| streamstats current=f last(ifInOctets) as p_ifInOctets last(ifOutOctets) as p_ifOutOctets by ifAlias             
| eval in_delta=(ifInOctets - p_ifInOctets)
| eval out_delta=(ifOutOctets - p_ifOutOctets)
| eval max=pow(2,64)
| eval out = if(out_delta<0,((max+out_delta)*8/(5*60*1000*1000*1000)),(out_delta)*8/(5*60*1000*1000*1000))
| timechart span=5m avg(in) AS in, avg(out) AS out by ifAlias
```
### "Field is immutable" error during helm upgrade

```
microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/charts/splunk-connect-for-snmp/ --namespace=sc4snmp --create-namespace
Error: UPGRADE FAILED: cannot patch "snmp-splunk-connect-for-snmp-inventory" with kind Job: Job.batch "snmp-splunk-connect-for-snmp-inventory" is invalid: (...) : field is immutable
```

The immutable error is due to the limitation placed on an inventory job. As the SC4SNMP requires several checks before applying updates, it is designed to allow changes in the inventory task after 5 minutes. 

The status of the inventory can be checked with the following command:
```
microk8s kubectl -n sc4snmp get pods | grep inventory
```
If the command is not empty, wait and execute it again after the inventory job finishes. This is when it is no longer visible in the output.

If the changes are required to be applied immediately, the previous inventory job can be deleted with the following command:
```
microk8s kubectl delete job/snmp-splunk-connect-for-snmp-inventory -n sc4snmp
```
The upgrade command can be executed again. 

### Identifying Traps issues

#### Wrong IP or port
The first possible answer to why traps are not sent to Splunk is that SNMP agents send trap messages to the wrong IP 
address or port. To check what is the correct address of traps server, run the following command:

```
microk8s kubectl -n sc4snmp get services
```

This command should output similar data:
```
NAME                                TYPE           CLUSTER-IP       EXTERNAL-IP      PORT(S)         AGE
snmp-redis-headless                 ClusterIP      None             <none>           6379/TCP        113s
snmp-mibserver                      ClusterIP      10.152.183.163   <none>           80/TCP          113s
snmp-mongodb                        ClusterIP      10.152.183.118   <none>           27017/TCP       113s
snmp-redis-master                   ClusterIP      10.152.183.61    <none>           6379/TCP        113s
snmp-mongodb-metrics                ClusterIP      10.152.183.50    <none>           9216/TCP        113s
snmp-splunk-connect-for-snmp-trap   LoadBalancer   10.152.183.190   114.241.233.134   162:32180/UDP   113s
```

Check the `EXTERNAL-IP` of `snmp-splunk-connect-for-snmp-trap` and the second port number for this service. In this case 
the full `snmp-splunk-connect-for-snmp-trap` address will be `114.241.233.134:32180`.


In case agents send traps to the correct address, but there is still no data in the `netops` index, there might be some
issues with credentials. These errors can be seen in logs of the `snmp-splunk-connect-for-snmp-trap` pod. 

#### Unknown SNMP community name encountered
In case of using community string for authentication purposes, the following error should be expected if the arriving trap 
has a community string not configured in SC4SNMP:
```
2024-02-06 15:42:14,885 ERROR Security Model failure for device ('18.226.181.199', 42514): Unknown SNMP community name encountered
```

If this error occurs, check if the appropriate community is defined under `traps.communities` in `values.yaml`. See the 
following example of a `public` community configuration:
```yaml
traps:
  communities:
    public:
      communityIndex:
      contextEngineId:
      contextName:
      tag:
      securityName:
```

#### Unknown SNMP security name encountered

While sending SNMP v3 traps in case of wrong username or engine id configuration, the following error should be expected: 
```
2024-02-06 15:42:14,091 ERROR Security Model failure for device ('18.226.181.199', 46066): Unknown SNMP security name encountered
```

If this error occurs, verify that the kubernetes secret with the correct username has been created ([SNMPv3 configuration](configuration/snmpv3-configuration.md)).
After creating the secret, add it under `traps.usernameSecrets` in `values.yaml`. Check that the correct snmp engine id
is configured under `traps.securityEngineId`. See the following example of a `values.yaml` with configured secret and engine id:
```yaml
traps:
  usernameSecrets:
    - my-secret-name
  securityEngineId:
    - "090807060504030201"
```

#### Authenticator mismatched

While sending SNMP v3 traps in case of wrong authentication protocol or password configuration, the following error should be expected: 
```
2024-02-06 15:42:14,642 ERROR Security Model failure for device ('18.226.181.199', 54806): Authenticator mismatched
```
If this error occurs, verify that the kubernetes secret with the correct authentication protocol and password has been created ([SNMPv3 configuration](configuration/snmpv3-configuration.md)).
After creating the secret, add it under `traps.usernameSecrets` in `values.yaml`. See the following example of a `values.yaml` with configured secret:
```yaml
traps:
  usernameSecrets:
    - my-secret-name
```

#### Ciphering services not available or ciphertext is broken
While sending SNMP v3 traps in case of wrong privacy protocol or password configuration, the following error should be expected: 
```
2024-02-06 15:42:14,780 ERROR Security Model failure for device ('18.226.181.199', 48249): Ciphering services not available or ciphertext is broken
```
If this error occurs, verify that the kubernetes secret with the correct privacy protocol and password has been created ([SNMPv3 configuration](configuration/snmpv3-configuration.md)).
After creating the secret, add it under `traps.usernameSecrets` in `values.yaml`. See the following example of a `values.yaml` with configured secret:
```yaml
traps:
  usernameSecrets:
    - my-secret-name
```
