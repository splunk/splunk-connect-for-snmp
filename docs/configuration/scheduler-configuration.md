# Scheduler configuration
Scheduler is a service with is responsible for manager schedules for SNMP walks and GETs. Schedules definition are store in Mongo DB. 
 
### Scheduler configuration file

Scheduler configuration is keep in `values.yaml` file in section `scheduler`.  To downland example file execute command:
```
curl -o ~/values.yaml https://raw.githubusercontent.com/splunk/splunk-connect-for-snmp/develop/values.yaml
```
`values.yaml` is being used during the installation process for configuring kubernetes values.

Example:
```yaml
scheduler:
  logLevel: "WARN"
  inventory_refresh_rate: "20"
  profiles: |
    match_test_profile:
      frequency: 5
            condition:
              type: "field"
              field: "SNMPv2-MIB.sysDescr"
              patterns: "^.*"
      varBinds:
        - ["SNMPv2-MIB", "sysDescr",0]
```

### Define log level
Log level for trap can be set by changing value for key `logLevel`. Allowed value are: `DEBUG`, `INFO`, `WARN`, `ERROR`. 
Default value is `WARN`

### Configure inventory refresh rate
`inventory_refresh_rate` - <TO_DO check what it does>

### Configure profile 
<TO_DO check it>
Profiles used in inventory can be created in `values.yaml`, which can be modified in scheduler config in `values.yaml`, ex.:
```yaml
scheduler:
  config: |
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
microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
```




