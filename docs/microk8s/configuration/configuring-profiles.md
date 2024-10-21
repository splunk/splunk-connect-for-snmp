# Configuring profiles

Profiles are where you can configure what you want to poll, and then assign them to the device. The definition of profile can be found in the `values.yaml` file
under the `scheduler` section.

See the following instructions on how to use profiles: [Update Inventory and Profile](../poller-configuration/#update-inventory). 

There are two types of profiles in general:

1. Static profile: Polling starts when the profile is added to the `profiles` field in the `inventory` of the device.
2. Smart profile: Polling starts when configured conditions are fulfilled, and the device to poll from has `smart_profiles` enabled in inventory.
Smart profiles are useful when you have many devices of the same kind, and you don't want to configure each of them individually with static profiles.
   
    In order to configure smart profile, do the following:
   
    1. Choose one of the fields polled from the device, most commonly sysDescr. 
    2. Set the filter to match all the devices of this kind.
    3. Set up polling of the profile by enabling the smart profiles for the devices that you want to be polled.

The profile template looks like the following:

```yaml
scheduler:
    profiles: |
      #Name of profile
      basev1:
        # Define frequency for profile
        frequency: 100
        #Define condition
        condition:
          # Define type of condition. Allowed value field, base and walk
          type: field
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

In the following example, two profiles are configured. One is smart, and the other one is static:

```yaml
scheduler:
    profiles: |
      smart_profile:
        frequency: 100
        condition:
          type: field
          field: "SNMPv2-MIB.sysDescr"
          patterns:
            - '.*linux.*'
        varBinds:
          - ['SNMPv2-MIB']
          - ['SNMPv2-MIB', 'sysName']
          - ['SNMPv2-MIB', 'sysUpTime',0]
      static_profile:
        frequency: 300
        varBinds:
          - ['IP-MIB']
```

If you only want to enable the option `static_profile` polling for the host `10.202.4.202`, you would configure a similar inventory:

```yaml
poller:
    inventory: |
      address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
      10.202.4.202,,2c,public,,,2000,static_profile,f,
```

If you want to enable checking the `10.202.4.202` device against smart profiles, you need to set `smart_profiles` to `t`:

```yaml
poller:
    inventory: |
      address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
      10.202.4.202,,2c,public,,,2000,,t,
```

Afterwards, if the device `sysDescr` matches the `'.*linux.*'` filter, the `smart_profile` profile will be polled.


## varBinds configuration
`varBinds` is short for "variable binding" in the SNMP. It is the combination of an Object Identifier (OID) and a value. 
`varBinds` are used for defining what OIDs should be requested from SNMP Agents. `varBinds` is a required 
subsection of each profile. The syntax configuration of `varBinds` looks like the following:

 [ "MIB-Component", "MIB object"[Optional], "MIB index number"[Optional]]
 
 - `MIB-Component`: The SNMP MIB itself consists of distinct component MIBs, each of which refers to a specific 
collection of management information that is part of the overall SNMP MIB, for example, `SNMPv2-MIB`. 
 If only the `MIB-Component` is set, then the SC4SNMP will get the whole subtree.
 - `MIB object`:  The SNMP MIB stores only simple data types: scalars and two-dimensional arrays of scalars, 
 called tables. The keywords SYNTAX, ACCESS, and DESCRIPTION as well as other keywords such as STATUS and 
 INDEX are used to define the SNMP MIB managed objects. 
 - `MIB index number`: Define the index number for a given MIB Object, for example,`0`.
 
See the following example:
```yaml
  varBinds:
    # Syntax: [ "MIB-Component", "MIB object name"[Optional], "MIB index number"[Optional]]
    - ['SNMPv2-MIB']
    - ['SNMPv2-MIB', 'sysName']
    - ['SNMPv2-MIB', 'sysUpTime',0]
```

## Static Profile configuration
Static Profile is used when a list of profiles is defined in the `poller` 
service [Inventory configuration](../poller-configuration/#configure-inventory). Static Profiles are executed 
even if the SmartProfile flag in inventory is set to false. 
To configure Static Profile, the following value needs to be set in the `profiles` section:

 - Define `ProfileName` as a subsection key in `profiles`.
 - Define `frequency` as the interval between SNMP execution in seconds.  
 - Define `varBinds` as var binds to query. 

See the following example:
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

### Particular kinds of static profiles

Sometimes static profiles have additional functionalities to be used in specific scenarios. 

#### WALK profile

If you would like to limit the scope of the walk, you should set one of the profiles in the inventory to point to the profile definition of the `walk` type:
```yaml
scheduler:
    profiles: |
      small_walk:
        condition: 
          type: "walk"
        varBinds:
          - ['UDP-MIB']
``` 
This profile should be placed in the profiles section of the inventory definition. It will be executed with the frequency defined in `walk_interval`.
If multiple profiles of type `walk` were placed in profiles, the last one will be used. 

See the following example on how to use `walk` in profiles:

```yaml
poller:
  inventory: |
    address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
    10.202.4.202,,2c,public,,,2000,small_walk,,
```

NOTE: When small walk is configured, `SNMPv2-MIB` is enabled by default (we need it to create the state of the device in the database).
For example, if you used `small_walk` from the previous example, you'll only be able to poll `UDP-MIB` and `SNMPv2-MIB` OIDs.


## SmartProfile configuration
SmartProfile is executed when the SmartProfile flag in the inventory is set to true and the conditions defined in profile match. 
See [Inventory configuration](../poller-configuration/#configure-inventory) for more information.

To configure SmartProfile, the following values needs to be set in the `profiles` section:

 - For`ProfileName`, define it as a subsection key in `profiles`. 
    - For`frequency`, define it as the interval between SNMP execution in seconds.
    - For `condition`, define the conditions to match the profile. 
       - For `type`, define it as the key for the `condition` section that defines the type of condition. The allowed values are `base` or `field` (`walk` type is also allowed here, but it's not part of smart profiles).
            - The `base` type of condition will be executed when `SmartProfile` in inventory is set to true.
            - The`field` type of condition will be executed if it matches `pattern` for the defined `field`. Supported fields are:
                -  "SNMPv2-MIB.sysDescr"
                -  "SNMPv2-MIB.sysObjectID"
        - For `field`, define the field name for the field condition type. 
        - For`pattern`, define the list of regular expression patterns for the MIB object field defined in the `field` section, for example:
                - ".*linux.*"
    - For `varBinds`, define var binds to query. 

See the following example of a `base` type profile:
```yaml
scheduler:
    profiles: |
      SmartProfile_base_example:
        frequency: 100
        condition: 
          type: "base"
        varBinds:
          - ['SNMPv2-MIB']
          - ['SNMPv2-MIB', 'sysName']
``` 

See the following example of a `field`  type profile, also called an automatic profile:
```yaml
scheduler:
    profiles: |
      SmartProfile_field_example:
        frequency: 100
        condition: 
          type: "field"
          field: "SNMPv2-MIB.sysDescr"
          patterns:
            - '.*STRING_TO_BE_MATCHED.*'
        varBinds:
          - ['SNMPv2-MIB']
          - ['SNMPv2-MIB', 'sysName']
``` 

NOTE: Be aware that profile changes may not be reflected immediately. It can take up to 1 minute for changes to propagate. In case you changed the frequency, or a profile type, the change will be reflected only after the next walk.
There is also a 5 minute time to live (TTL) for an inventory pod. SC4SNMP allows one inventory upgrade and then it block updates for the next 5 minutes.

## Conditional profiles
There is a way to not explicitly list what SNMP objects you want to poll, but, instead, only give the conditions that must be fulfilled to
qualify an object for polling.

See the following example of a conditional profile:

```yaml
IF_conditional_profile:
  frequency: 30
  conditions:
    - field: IF-MIB.ifAdminStatus
      operation: "equals" 
      value: "up"
    - field: IF-MIB.ifOperStatus
      operation: "equals"
      value: "up"
  varBinds:
    - [ 'IF-MIB', 'ifDescr' ]
    - [ 'IF-MIB', 'ifAlias' ]
    - [ 'IF-MIB', 'ifInErrors' ]
    - [ 'IF-MIB', 'ifOutDiscards' ]
```

When the such profile is defined and added to a device in an inventory, it will poll all interfaces where `ifAdminStatus`
and `ifOperStatus` is up. Conditional profiles are being evaluated during the walk process (on every `walk_interval`),
and, if the status changes in between, the scope of the conditional profile won't be modified. Therefore, status changes are only implemented when walk_interval is executed.

See the following operations that can be used in conditional profiles: 

1. `equals`: the value gathered from `field` is equal to the`value`.
2. `gt`: the value gathered from `field` is bigger than `value` (works only for numeric values).
3. `lt`: the value gathered from `field` is smaller than `value` (works only for numeric values).
4. `in`: the value gathered from `field` is equal to one of the elements provided in `value`, for example:

```yaml
conditions:
  - field: IF-MIB.ifAdminStatus
    operation: "in"
    value: 
      - "down"
      - 0
```

5. `regex`: value gathered from `field` match the pattern provided in `value`. 
You can add options for regular expression after `/`. Possible options match ones used in [mongodb regex operator](https://www.mongodb.com/docs/manual/reference/operator/query/regex/), for example: 

```yaml
conditions:
  - field: IF-MIB.ifAdminStatus
    operation: "regex"
    value: ".own/i"
```

To negate an operation you can add the flag `negate_operation: "true"` to the specified `field`, for example: 
```yaml
conditions:
    - field: IF-MIB.ifAdminStatus
      operation: "equals" 
      value: "up"
      negate_operation: "true"
```
This will negate the operator specified in `operation`. See the following: 

1. `negate_operation + equals`: value gathered from `field` is NOT equal to `value`.
2. `negate_operation + gt`: value gathered from `field` is SMALLER or EQUAL to `value` (works only for numeric values).
3. `negate_operation + lt`: value gathered from `field` is BIGGER or EQUAL to `value` (works only for numeric values).
4. `negate_operation + in`: value gathered from `field` is NOT equal to any of the elements provided in `value`.
5. `negate_operation + regex`: value gathered from `field` is NOT matching the pattern provided in `value`. 

The `field` parameter in `conditions` must fulfill the pattern `MIB-family.field`. The field must represent a textual value (rather than a metric one).
See [snmp data format](snmp-data-format.md) for more information. 

You have to explicitly define `varBinds` (not only the MIB family but also the field to poll). See the following **incorrect** example: 

```yaml
varBinds:
- [ 'IF-MIB' ]
```


## Custom translations
If the user wants to use custom names/translations of MIB names, it can be configured under the customTranslations section under scheduler config.
Translations are grouped by the MIB family. In the following example, IF-MIB.ifInDiscards will be translated to IF-MIB.myCustomName1:
```yaml
scheduler:
    customTranslations:
      IF-MIB:
        ifInDiscards: myCustomName1
        ifOutErrors: myCustomName2
      SNMPv2-MIB:
        sysDescr: myCustomName3
```

