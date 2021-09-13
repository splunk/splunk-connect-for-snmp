### Test SNMP Traps

-   Test the trap from a linux system with snmp installed replace the ip
    `10.0.101.22` with the shared ip above

``` bash
apt-get install snmpd
snmptrap -v2c -c public 10.0.101.22 123 1.3.6.1.6.3.1.1.5.1 1.3.6.1.2.1.1.5.0 s test
```

-   Search splunk, one event per trap command with the host value of the
    test machine ip will be found

``` bash
index=em_logs sourcetype="sc4snmp:traps"
```

### Setup Poller

-   Test the poller by logging to Splunk and confirm presence of events
    in snmp `em_logs` and metrics in `em_metrics` index.

### Inventory
\* You can change the inventory contents in values.yaml, in scheduler inventory field, ex.:
```
  inventory:
    content: |-
      10.0.101.22,2c,public,basev1,300
```
Where 10.0.101.22 is a host IP.

Content below is interpreted as csv file with following
columns:

1.  host (IP or name)
2.  version of SNMP protocol
3.  community string authorisation phrase
4.  profile of device (varBinds of profiles can be found in config.yaml, defined in scheduler config in values.yaml)
5.  frequency in seconds (how often SNMP connector should ask agent for
    data)

### Config
Profiles used in inventory can be created in `config.yaml`, which can be modified in scheduler config in `values.yaml`, ex.:
```
scheduler:
  logLevel: "WARN"
  ...
  config: |
    celery:
    ...
    profiles:
      basev1:
        varBinds:
          # Syntax: [ "MIB-Files", "MIB object name" "MIB index number"]
          - ['SNMPv2-MIB', 'sysDescr']
          - ['SNMPv2-MIB', 'sysUpTime',0]
          - ['SNMPv2-MIB', 'sysName']
```


Every change in values.yaml file can be applied with the command:
``` bash
$ microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/snmp-installer --namespace=sc4snmp --create-namespace
Release "snmp" has been upgraded. Happy Helming!
NAME: snmp
LAST DEPLOYED: Thu Sep  9 10:54:04 2021
NAMESPACE: sc4snmp
STATUS: deployed
REVISION: 2
TEST SUITE: None
```

More information about how to configure `values.yaml` is available here: [Additional HELM values](additional-helm-configuration.md)
### Test Poller

Search splunk, one event per trap command with the host value of the
test machine ip will be found

``` bash
index=em_meta sourcetype="sc4snmp:meta" SNMPv2_MIB__sysLocation_0="*" | dedup host
```

``` bash
| mcatalog values(metric_name)  where index=em_metrics AND metric_name=sc4snmp* AND host=<hostname>
```

### Maintain

Manage configuration obtain and update communities, user/secrets and
inventories