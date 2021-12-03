
### Create SNMP v3 users

Configuration of SNMP v3 when supported by the monitored devices is the most secure choice available
for authentication and data privacy. Each set of credentials will be stored as "Secret" objects in k8s
and will be referenced in the values.yaml. This allows the secret to be created once including automation
by third party password managers then consumed without storing sensitive data in plain text.

```bash
# <secretname>=Arbitrary name of the secret often the same as the username or prefixed with "sc4snmp-"
# <namespace>=Namespace used to install sc4snmp
# <username>=the SNMPv3 Username
# <key>=key note must be at least 8 char long subject to target limitations
# <authProtocol>=One of SHA (SHA1) or MD5 
# <privProtocol>=One of AES or DES 
# Note MD5 and DES are considered insecure but must be supported for standards compliance
kubectl create -n <namespace> secret generic <secretname> \
  --from-literal=username=<username> \
  --from-literal=authKey=<key> \
  --from-literal=privKey=<key> \
  --from-literal=authProtocol=<authProtocol> \
  --from-literal=privProtocol=<privProtocol> \
```

### Test SNMP Traps

-   Test the trap from a linux system with SNMP installed. Replace the IP address 
    `10.0.101.22` with the shared IP address above

``` bash
apt-get install snmpd
snmptrap -v2c -c public 10.0.101.22 123 1.3.6.1.6.3.1.1.5.1 1.3.6.1.2.1.1.5.0 s test
```

-   Search splunk: You should see one event per trap command with the host value of the
    test machine IP address

``` bash
index=em_logs sourcetype="sc4snmp:traps"
```

### Setup Poller

-   Test the poller by logging into Splunk and confirm the presence of events
    in snmp `em_logs` and metrics in `em_metrics` index

### Inventory
\* You can change the inventory contents in `config_values.yaml`, in scheduler inventory field, ex.:
```
files:
  scheduler:
    inventory: |
      address,version,community,walk_interval,profiles,SmartProfiles,delete
      10.0.0.1,2c,homelab,300,,,
```
Where 10.0.101.22 is a host IP.

Content below is interpreted as a .csv file with the following
columns:

1.  host (IP or name)
2.  version of SNMP protocol
3.  community string authorisation phrase
4.  profile of device (varBinds of profiles can be found in config.yaml, defined in scheduler config in values.yaml),
    for automatic profile assignment '*' can be used, profile name may contain only letters, numbers, underscore or dash


### Config
Profiles used in inventory can be created in `config_values.yaml`, which can be modified in scheduler config in `values.yaml`, ex.:
```
files:
  scheduler:
    config: |
      celery:
      ...
      profiles:
        basev1:
          frequency: 10
          patterns:
            - '.*STRING_TO_BE_MATCHED.*'
          varBinds:
            # Syntax: [ "MIB-Files", "MIB object name" "MIB index number"]
            - ['SNMPv2-MIB', 'sysDescr']
            - ['SNMPv2-MIB', 'sysUpTime',0]
            - ['SNMPv2-MIB', 'sysName']
```
frequency - frequency in seconds (how often SNMP connector should ask agent for data)
patterns - list of regular expressions that will be matched against sysDescr or sysObjectId

Every change in values.yaml file can be applied with the command:
``` bash
microk8s helm3 upgrade --install snmp -f deployment_values.yaml -f config_values.yaml -f static_values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
```

This command should produce this kind of output:
```
Release "snmp" has been upgraded. Happy Helming!
NAME: snmp
LAST DEPLOYED: Thu Sep  9 10:54:04 2021
NAMESPACE: sc4snmp
STATUS: deployed
REVISION: 2
TEST SUITE: None
```

More information about how to configure `deployment_values.yaml` is available here: [Additional HELM values](additional-helm-configuration.md)
### Test Poller

Search splunk: You should see one event per trap command with the host value of the
test machine IP address

``` bash
index=em_meta sourcetype="sc4snmp:meta" SNMPv2_MIB__sysLocation_0="*" | dedup host
```

``` bash
| mcatalog values(metric_name)  where index=em_metrics AND metric_name=sc4snmp* AND host=<hostname>
```

### Maintain

Manage configuration, obtain and update communities, user/secrets and
inventories
