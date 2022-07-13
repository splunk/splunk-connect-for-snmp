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
If you would like to limit the scope of the walk, you should set one of the profiles in the inventory to point to the profile definition of type `walk`
```yaml
scheduler:
    profiles: |
      small_walk:
        condition: 
          type: "walk"
        varBinds:
          - ['UDP-MIB']
``` 
Such profile should be placed in the profiles section of inventory definition. It will be executed with the frequency defined in walk_interval.
In case of multiple profiles of type `walk` will be placed in profiles, the last one will be used.

```yaml
poller:
  inventory: |
    address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
    10.202.4.202,,2c,public,,,2000,small_walk,,
```

NOTE: When small walk is configured, you can set up polling only of OIDs belonging to walk profile varBinds. 
Additionally, there are two MIB families that are enabled by default (we need them to create state of the device in the database and poll base profiles): `IF-MIB` and `SNMPv2-MIB`.
For example, if you've decided to use `small_walk` from the example above, you'll be able to poll only `UDP-MIB`, `IF-MIB` and `SNMPv2-MIB` OIDs.
