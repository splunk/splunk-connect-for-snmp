# Configuring profiles

Profiles are the units where you can configure what you want to poll, and then assign them to the device. The definition of profile can be found in the `values.yaml` file
under the `scheduler` section.

Here are the instructions on how to use profiles: [Update Inventory and Profile](../poller-configuration/#update-inventory). 

There are two types of profiles in general:

1. Static profile - polling starts when the profile is added to the `profiles` field in the `inventory` of the device.
2. Smart profile - polling starts when configured conditions are fulfilled, and the device to poll from has `smart_profiles` enabled in inventory.
Smart profiles are useful when we have many devices of a certain kind, and we don't want to configure each of them individually with static profiles.
   
    In order to configure smart profile, do the following:
   
    1. Choose one of the fields polled from the device, most commonly sysDescr. 
    2. Set the filter to match all the devices of this kind.
    3. Setup polling of the profile by enabling smart profiles for devices you want to be polled.

The template of the profile looks like the following:

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

For example, we have configured two profiles. One is smart, and the other one is static:

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

If we want to enable only `static_profile` polling for the host `10.202.4.202`, we will configure similar inventory:

```yaml
poller:
    inventory: |
      address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
      10.202.4.202,,2c,public,,,2000,static_profile,f,
```

If we want to enable checking the `10.202.4.202` device against smart profiles, we need to set `smart_profiles` to `t`:

```yaml
poller:
    inventory: |
      address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
      10.202.4.202,,2c,public,,,2000,,t,
```

Then, if the device `sysDescr` matches the `'.*linux.*'` filter, the `smart_profile` profile will be polled.


## varBinds configuration
`varBinds` is short for "variable binding" in the SNMP. It is the combination of an Object Identifier (OID) and a value. 
`varBinds` are used for defining what OIDs should be requested from SNMP Agents. `varBinds` is a required 
subsection of each profile. The syntax configuration of `varBinds` looks like the following:

 [ "MIB-Component", "MIB object"[Optional], "MIB index number"[Optional]]
 
 - `MIB-Component` - The SNMP MIB itself consists of distinct component MIBs, each of which refers to a specific 
 defined collection of management information that is part of the overall SNMP MIB, eg., `SNMPv2-MIB`. 
 If only the `MIB-Component` is set, then the SC4SNMP will get the whole subtree.
 - `MIB object` -  The SNMP MIB stores only simple data types: scalars and two-dimensional arrays of scalars, 
 called tables. The keywords SYNTAX, ACCESS, and DESCRIPTION as well as other keywords such as STATUS and 
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

## Static Profile configuration
Static Profile is used when they are defined on a list of profiles in the inventory configuration in the `poller` 
service [Inventory configuration](../poller-configuration/#configure-inventory). Static Profiles are executed 
even if the SmartProfile flag in inventory is set to false. 
To configure Static Profile value needs to be set in the `profiles` section:

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

### Particular kinds of static profiles

Sometimes static profiles have additional functionalities to be used in specific scenarios. 

#### WALK profile

If you would like to limit the scope of the walk, you should set one of the profiles in the inventory to point to the profile definition of type `walk`:
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
If multiple profiles of type `walk` is placed in profiles, the last one will be used. 

This is how to use `walk` profiles:

```yaml
poller:
  inventory: |
    address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
    10.202.4.202,,2c,public,,,2000,small_walk,,
```

NOTE: When small walk is configured, you can set up polling only of OIDs belonging to the walk profile varBinds. 
Additionally, there are two MIB families that are enabled by default (we need them to create the state of the device in the database and poll base profiles): `IF-MIB` and `SNMPv2-MIB`.
For example, if you've decided to use `small_walk` from the example above, you'll be able to poll only `UDP-MIB`, `IF-MIB`, and `SNMPv2-MIB` OIDs.


## SmartProfile configuration
SmartProfile is executed when the SmartProfile flag in inventory is set to true and the condition defined in profile match. 
More information about configuring inventory can be found in [Inventory configuration](../poller-configuration/#configure-inventory).

To configure Smart Profile, the following value needs to be set in the `profiles` section:

 - `ProfileName` - define as subsection key in `profiles`. 
    - `frequency` - define an interval between executing SNMP's gets in second.
    - `condition` - section define conditions to match profile
        - `type` - key of `condition` section which defines type of condition. The allowed values are `base` and `field` (`walk` type is also allowed here, but it's not part of smart profiles).
            - `base` type of condition will be executed when `SmartProfile` in inventory is set to true.
            - `field` type of condition will be executed if it matches `pattern` for defined `field`. Supported fields are:
                -  "SNMPv2-MIB.sysDescr"
                -  "SNMPv2-MIB.sysObjectID"
        - `field` Define field name for condition type field. 
        - `pattern` Define list of regular expression patterns for MIB object field defined in `field` section. For example:
                - ".*linux.*"
    - `varBinds` - define var binds to query. 

Example of `base` type profile:
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

Example of `field`  type profile, also called an automatic profile:
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

NOTE: Be aware that profile changes may not be reflected immediately. It can take up to 1 minute for changes to propagate. In case you changed frequency, or a profile type, the change will be reflected only after the next walk.
There is also 5 minute TTL for an inventory pod. Basically, SC4SNMP allows one inventory upgrade and then block updates for the next 5 minutes.

## Conditional profiles
There is a way to not explicitly give what SNMP objects we want to poll - only the conditions that must be fulfilled to
qualify object for polling.

The example of a conditional profile is:

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

When such profile is defined and added to a device in an inventory, it will poll all interfaces where `ifAdminStatus`
and `ifOperStatus` are up. Note that conditional profiles are being evaluated during the walk process (on every `walk_interval`)
and if the status changes in between, the scope of the conditional profile won't be modified.

These are operations possible to use in conditional profiles:

1. `equals` - value gathered from `field` is equal to `value`
2. `gt` - value gathered from `field` is bigger than `value` (works only for numeric values)
3. `lt` - value gathered from `field` is smaller than `value` (works only for numeric values)
4. `in` - value gathered from `field` is equal to one of the element provided in `value`, for ex.:

```yaml
conditions:
  - field: IF-MIB.ifAdminStatus
    operation: "in"
    value: 
      - "down"
      - 0
```

`field` part of `conditions` must fulfill the pattern `MIB-family.field`. Fields must represent textual value (not metric one),
you can learn more about it [here](snmp-data-format.md).

You have to explicitly define `varBinds` (not only the MIB family, but also the field to poll), so such config:

```yaml
varBinds:
- [ 'IF-MIB' ]
```

is not correct.



## Custom translations
If the user wants to use custom names/translations of MIB names, it can be configured under the customTranslations section under scheduler config.
Translations are grouped by MIB family. In the example below IF-MIB.ifInDiscards will be translated to IF-MIB.myCustomName1:
```yaml
scheduler:
    customTranslations:
      IF-MIB:
        ifInDiscards: myCustomName1
        ifOutErrors: myCustomName2
      SNMPv2-MIB:
        sysDescr: myCustomName3
```

