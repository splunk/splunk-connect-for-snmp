# Debug Splunk Connect for SNMP

## Pieces of Advice

### Check when SNMP WALK was executed last time for device
1. [Configure Splunk OpenTelemetry Collector for Kubernetes](gettingstarted/sck-installation.md)
2. Go to your Splunk and execute search: `index="em_logs"   "Sending due task" "sc4snmp;<IP_ADDRESS>;walk"` 
and replace <IP_ADDRESS> by IP Address which you are interested. 

### Uninstall Splunk Connect for SNMP
To uninstall SC4SNMP run the following commands:

```
 microk8s helm3 uninstall snmp -n sc4snmp
 microk8s kubectl delete pvc --all -n sc4snmp
```

### Installing Splunk Connect for SNMP on Linux RedHat 
Installation of RedHat may be blocking ports required by microk8s. Installing microk8s on RedHat 
required checking if the firewall is not blocking any of [required microk8s ports](https://microk8s.io/docs/ports). 

## Issues

### "Empty SNMP response message" problem
In case you see the following line in worker's logs:

```log
[2022-01-04 11:44:22,553: INFO/ForkPoolWorker-1] Task splunk_connect_for_snmp.snmp.tasks.walk[8e62fc62-569c-473f-a765-ff92577774e5] retry: Retry in 3489s: SnmpActionError('An error of SNMP isWalk=True for a host 192.168.10.20 occurred: Empty SNMP response message')
```
that causes infinite retry of walk operation, add `worker.ignoreEmptyVarbinds` parameter to `values.yaml` and set it to true.

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

If you put only IP address (ex. `127.0.0.1`), then errors will be ignored for all of its devices (like `127.0.0.1:161`, 
`127.0.0.1:163`...). If you put IP address and host structured as `{host}:{port}` that means the error will be ignored only for this device.

### Walking a device takes too much time

Enable small walk functionality with the following instruction: [Configure small walk profile](../configuration/configuring-profiles/#walk-profile). 

### An error of SNMP isWalk=True blocks traffic on SC4SNMP instance

If you see many `An error of SNMP isWalk=True` errors in logs, that means that there is a connection problem with the hosts you're polling from.
Walk will try to retry multiple times, what will eventually cause a worker to be blocked for the retries time. In this case, you might want to limit
the maximum retries time. You can do it by setting the variable `worker.walkRetryMaxInterval`, like:

```yaml
worker:
  walkRetryMaxInterval: 60
```

With the configuration from the above, walk will retry exponentially until it reaches 60 seconds.