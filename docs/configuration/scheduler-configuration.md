# Scheduler configuration
Scheduler is a service with is responsible for manager schedules for SNMP walks and GETs. Schedules definition 
are store in Mongo DB. 
 
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
  profiles: |
    test_profile:
      frequency: 5 
      condition: 
        type: "field" 
        field: "SNMPv2-MIB.sysDescr" 
        patterns: 
          - "^.*"
      varBinds:
          # Syntax: [ "MIB-Component", "MIB object name"[Optional], "MIB index number"[Optional]]
        - ["SNMPv2-MIB", "sysDescr",0]
```

### Define log level
Log level for trap can be set by changing value for key `logLevel`. Allowed value are: `DEBUG`, `INFO`, `WARNING`, `ERROR`. 
Default value is `WARNING`

### Define resource requests and limits
```yaml
scheduler:
  #The following resource specification is appropriate for most deployments to scale the
  #Larger inventories may require more memory but should not require additional cpu
  resources:
    limits:
        cpu: 1
        memory: 1Gi
    requests:
      cpu: 200m
      memory: 128Mi
```
### Configure profile 
Profiles used in inventory can be created in `values.yaml`, which can be modified in scheduler config in 
`values.yaml`, ex.:
```yaml
scheduler:
    profiles: |
      #Name of profile
      basev1:
        # Define frequency for profile
        frequency: 10
        #Define condition
        condition:
          # Define type of condition. Allowed value field and base 
          typy: field
          field: "SNMPv2-MIB.sysDescr"
          # Define paterns
          patterns:
            - '.*STRING_TO_BE_MATCHED.*'
        #Define varbinds to query
        varBinds:
          # Syntax: [ "MIB-Component", "MIB object name"[Optional], "MIB index number"[Optional]]
          - ['SNMPv2-MIB']
          - ['SNMPv2-MIB', 'sysName']
          - ['SNMPv2-MIB', 'sysUpTime',0]
```

#### varBinds configuration
`varBinds` short for "variable binding" in SNMP. The combination of an Object Identifier (OID) and a value. 
`varBinds` are use for defining in profiles what OIDs should be getting from SNMP Agents. `varBinds` is required 
subsection of each profile. Syntax configuration of `varBinds` looks following:

 [ "MIB-Component", "MIB object"[Optional], "MIB index number"[Optional]]
 
 - `MIB-Component` - The SNMP MIB, itself, consists of distinct component MIBs, each of which refers to a specific 
 defined collection of management information that is part of the overall SNMP MIB eg. `SNMPv2-MIB`. 
 If only `MIB-Component` is set than all whole sub tree is getting.
 - `MIB object` -  The SNMP MIB stores only simple data types: scalars and two-dimensional arrays of scalars, 
 called tables. Keywords SYNTAX, ACCESS, and DESCRIPTION as well as other keywords such as STATUS and 
 INDEX are used to define the SNMP MIB managed objects. 
 - `MIB index number` - Define index number for given MIB Object eg. `0`.
 
Example:
```yaml
  varBinds:
    # Syntax: [ "MIB-Component", "MIB object name"[Optional], "MIB index number"[Optional]]
    - ['SNMPv2-MIB']
    - ['SNMPv2-MIB', 'sysName']
    - ['SNMPv2-MIB', 'sysUpTime',0]
```

#### Static Profile configuration
Static Profile are used when they are defined on list of profile in inventory configuration in `poller` 
service [Inventory configuration](../poller-configuration/#configure-inventory). Static Profile are executed 
even if SmartProfile flag in inventory is set to false. 
To configure Static Profile following value need to be set in `profiles` section:

 - `ProfileName` - define as subsection key in `profiles`. 
    - `frequency` - define interval between executing SNMP gets in second.  
    -  `varBinds` - define var binds to query. 

Example:
```yaml
scheduler:
  profiles: |
    static_profile_example:
      frequency: 20
      varBinds:
        - ['SNMPv2-MIB']
        - ['SNMPv2-MIB', 'sysName']
        - ['SNMPv2-MIB', 'sysUpTime',0]
```

#### SmartProfile configuration
SmartProfile are executed when SmartProfile flag in inventory is set to true and condition defined in profile matching. 
More information about configuring inventory can be found in [Inventory configuration](../poller-configuration/#configure-inventory)

To configure Static Profile following value need to be set in `profiles` section:

 - `ProfileName` - define as subsection key in `profiles`. 
    - `frequency` - define interval between executing SNMP gets in second.
    - `condition` - section define conditions to much profile
        - `type` - key of `condition` section which defines type of condition. Allowed value `base` and `field`. 
            - `base` type of condition will be executed always when `SmartProfile` in inventory is set to true.
            - `field` type of condition will be executed if match `pattern` for defined `field`. Supported fields:
                -  "SNMPv2-MIB.sysDescr"
                -  "SNMPv2-MIB.sysObjectID"
        - `field` Define field name for condition type field. 
        - `pattern` Define list of regular expression pattern for MIB object field defined in `field` section. <TO_DO add any :)>
    - `varBinds` - define var binds to query. 

Example of `base` type of condition
```yaml
scheduler:
    profiles: |
      SmartProfile_base_example:
        frequency: 10
        condition: 
          typy: "base"
        varBinds:
          - ['SNMPv2-MIB']
          - ['SNMPv2-MIB', 'sysName']
``` 

Example of `field` type of condition
```yaml
scheduler:
    profiles: |
      SmartProfile_field_example:
        frequency: 10
        condition: 
          typy: "field"
          field: "SNMPv2-MIB.sysDescr"
          patterns:
            - '.*STRING_TO_BE_MATCHED.*'
        varBinds:
          - ['SNMPv2-MIB']
          - ['SNMPv2-MIB', 'sysName']
``` 




