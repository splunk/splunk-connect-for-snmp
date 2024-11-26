# Identifying Polling and Walk Issues

## Check when SNMP WALK was executed last time for the device
1. [Configure Splunk OpenTelemetry Collector for Kubernetes](../microk8s/sck-installation.md) or [Configure Docker Logs for Splunk](../dockercompose/9-splunk-logging.md).
2. Go to your Splunk and execute search: `index="em_logs"   "Sending due task" "sc4snmp;<IP_ADDRESS>;walk"` 
and replace <IP_ADDRESS> with the pertinent IP Address. 

## "Empty SNMP response message" problem
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

## "OID not increasing" problem
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

## Walking a device takes too much time

See [Configure small walk profile](../../microk8s/configuration/configuring-profiles/#walk-profile) to enable the small walk 
functionality.

## An error of SNMP isWalk=True blocks traffic on the SC4SNMP instance

If you see many `An error of SNMP isWalk=True` errors in your logs, that means that there is a connection problem 
with the hosts you are polling from.
Walk will retry multiple times, which will eventually cause a worker to be blocked while it retries. In that case, you might want to limit
the maximum retry time. You can do this by setting the variable `worker.walkRetryMaxInterval`, for example:

```yaml
worker:
  walkRetryMaxInterval: 60
```

With the previous configuration, 'walk' will retry exponentially from 30 seconds until it reaches 60 seconds. The default value for `worker.walkRetryMaxInterval` is 180.

## SNMP Rollover
The Rollover problem is due to a finite stored integer value (especially when the value is 32-bit). 
When it reaches its maximum, it gets rolled down to 0 again. This causes a strange drop in Analytics data.
The most common case of this issue is interface speed on high speed ports. As a solution to this problem, SNMPv2 SMI defined a new object type, counter64, for 64-bit counters, see https://www.cisco.com/c/en/us/support/docs/ip/simple-network-management-protocol-snmp/26007-faq-snmpcounter.html.
Not all the devices support it, but if they do, poll the counter64 type OID instead of the counter32 one. 
For example, use `ifHCInOctets` instead of `ifInOctets`.

If 64-bit counter is not supported on your device, you can write your own Splunk queries that calculate the shift based on
the maximum integer value and the current state. The same works for values large enough that they don't fit into a 64-bit value.
An example for an appropriate Splunk query would be the following:

```
| streamstats current=f last(ifInOctets) as p_ifInOctets last(ifOutOctets) as p_ifOutOctets by ifAlias             
| eval in_delta=(ifInOctets - p_ifInOctets)
| eval out_delta=(ifOutOctets - p_ifOutOctets)
| eval max=pow(2,64)
| eval out = if(out_delta<0,((max+out_delta)*8/(5*60*1000*1000*1000)),(out_delta)*8/(5*60*1000*1000*1000))
| timechart span=5m avg(in) AS in, avg(out) AS out by ifAlias
```

## Polling authentication errors

### Unknown USM user
In case of polling SNMPv3 devices, `Unknown USM user` error suggests wrong username. Verify 
that the kubernetes secret with the correct username has been created ([SNMPv3 configuration](../microk8s/configuration/snmpv3-configuration.md)).

### Wrong SNMP PDU digest
In case of polling SNMPv3 devices, `Wrong SNMP PDU digest` error suggests wrong authentication key. Verify 
that the kubernetes secret with the correct authentication key has been created ([SNMPv3 configuration](../microk8s/configuration/snmpv3-configuration.md)).

### No SNMP response received before timeout
`No SNMP response received before timeout` error might have several root causes. Some of them are:

- wrong device IP or port
- SNMPv2c wrong community string
- SNMPv3 wrong privacy key

## "Field is immutable" error during helm upgrade

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

## "The following profiles have invalid configuration" or "The following groups have invalid configuration" errors
Following errors are examples of wrong configuration:
```
The following groups have invalid configuration and won't be used: ['group1']. Please check indentation and keywords spelling inside mentioned groups configuration.
```
```
The following profiles have invalid configuration and won't be used: ['standard_profile', 'walk_profile']. Please check indentation and keywords spelling inside mentioned profiles configuration.
```
Errors above indicate, that the mentioned groups or profiles might have wrong indentation or some keywords were omitted or misspelled. Refer to:

- kubernetes: [Configuring profiles](../microk8s/configuration/configuring-profiles.md) or [Configuring Groups](../microk8s/configuration/configuring-groups.md)
- docker: [Scheduler configuration](../dockercompose/4-scheduler-configuration.md)

sections to check how the correct configuration should look like.