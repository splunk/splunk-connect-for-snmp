# Debug Splunk Connect for SNMP

## Advices

### Check when SNMP WALK was executed last time for device
1. [Configure SCK](gettingstarted/sck-installation.md)
2. Go to your Splunk and execute search: `index="em_logs"   "Sending due task" "sc4snmp;<IP_ADDRESS>;walk"` 
and replace <IP_ADDRESS> by IP Address which you are interested. 

### Uninstall Splunk Connect for SNMP
To uninstall SC4SNMP run following commands:

```
 microk8s helm3 uninstall snmp -n sc4snmp
 microk8s kubectl delete pvc --all -n sc4snmp
```

### Installing Splunk Connect for SNMP on Linux RedHat 
Installation of RedHat may blocking ports required by microk8s. Installing microk8s on RedHat 
required to check if firewall is not blocking any of [required microk8s ports](https://microk8s.io/docs/ports). 

## Issues

### "Empty SNMP response message" problem
In case you see the following line in worker's logs:

```log
[2022-01-04 11:44:22,553: INFO/ForkPoolWorker-1] Task splunk_connect_for_snmp.snmp.tasks.walk[8e62fc62-569c-473f-a765-ff92577774e5] retry: Retry in 3489s: SnmpActionError('An error of SNMP isWalk=True for a host 192.168.10.20 occurred: Empty SNMP response message')
```

that causes infinite retry of walk operation, add `worker.ignoreEmptyVarbinds` parameter to `values.yaml` and set it to true.

An example confiuration for worker in `values.yaml` is:

```yaml
worker:
  ignoreEmptyVarbinds: true
```