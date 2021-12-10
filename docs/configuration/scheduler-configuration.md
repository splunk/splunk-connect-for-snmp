# Scheduler configuration
Scheduler is a service which is responsible for managing schedules for SNMP walks and polls. Schedules definition 
are stored in Mongo DB. 
 
### Scheduler configuration file

Scheduler configuration can be found in `values.yaml` file under `scheduler` section. To downland example file execute following command:
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

### Defining log level
Log level for scheduler can be set by changing value for key `logLevel`. Allowed values are: `DEBUG`, `INFO`, `WARN`, `ERROR`. 
Default value is `WARN`

### Configuring profiles 
Profiles used in inventory can be created and modified in `profiles` section which is part of scheduler configuration, ex.:

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
`varBinds` are used for defining in profiles what OIDs should be requested from SNMP Agents. `varBinds` is a required 
subsection of each profile. `varBinds` configuration syntax is following:

 [ "MIB-Component", "MIB object"[Optional], "MIB index number"[Optional]]
 
 - `MIB-Component` - The SNMP MIB, itself, consists of distinct MIBs components, each of which refers to a specific 
 defined collection of management information that is part of the overall SNMP MIB eg. `SNMPv2-MIB`. 
 If only `MIB-Component` is set then whole sub tree will be requested.
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
Static Profiles will be used when they are added on list of `profiles` in `poller` inventory configuration  [Inventory configuration](../poller-configuration/#configure-inventory).
Static Profiles are executed regardless of the current setting of `SmartProfiles` flag in inventory. 
To configure Static Profile following values need to be configured in `profiles` section:

 - `ProfileName` - define as subsection key in `profiles`. 
    - `frequency` - define an interval between executing SNMP polls in seconds.  
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

#### SmartProfiles profile configuration
SmartProfiles are executed when `SmartProfiles` flag in inventory is set to true and condition defined in a given profile is matching. 
More information about configuring inventory can be found in [Inventory configuration](../poller-configuration/#configure-inventory)

To configure Static Profile following values need to be set in `profiles` section:

 - `ProfileName` - define as subsection key in `profiles`. 
    - `frequency` - define an interval between executing SNMP gets in seconds.
    - `condition` - section define conditions to match profile
        - `type` - key of `condition` section which defines type of condition. Allowed value `base` and `field`. 
            - `base` type of condition, will always be executed when `SmartProfiles` flag in inventory is set to true.
            - `field` type of condition, will be executed if `pattern` is matched for defined `field`.
        - `field` Define field name for condition type `field`. Determines on which field `pattern` matching will be done. Supported fields:
                -  "SNMPv2-MIB.sysDescr"
                -  "SNMPv2-MIB.sysObjectID"
        - `patterns` Define list of regular expression patterns which will be used for matching.
    - `varBinds` - define var binds to poll. 

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




