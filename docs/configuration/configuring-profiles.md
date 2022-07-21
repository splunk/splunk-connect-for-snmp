# Configuring profiles

Profiles are the units, where you can configure what you want to poll and then assign them to the device. The definition of profile lays in `values.yaml` file
under the `scheduler` section.

Here is the instruction of how to use profiles: [Update Inventory and Profile](../deployment-configuration/#update-inventory-and-profile). 

There are two types of profiles in general:

1. Static profile - polling starts when profile is added to `profiles` field in `inventory` of the device
2. Smart profile - polling starts when configured conditions are fulfilled, and the device to poll from has `smart_profiles` enabled in inventory.
Smart profiles are useful when we have many devices of certain kind, and we don't want to configure all of them "one by one" with static profiles.
   In order to do so, we elect one of the fields (most commonly `sysDescr`), set the filter to match all the devices of this kind and setup polling of the profile.

The template of the profile looks like following:

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

For example, we have configured two profiles. One is smart, the other one is static:

```yaml
scheduler:
    profiles: |
      smart_profile:
        frequency: 10
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

If we want to enable only `static_profile` polling for host `10.202.4.202`, we will configure inventory like that:

```yaml
poller:
    inventory: |
      address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
      10.202.4.202,,2c,public,,,2000,static_profile,f,
```

If we want to enable checking `10.202.4.202` device against smart profiles, we need to set `smart_profiles` to `t`:

```yaml
poller:
    inventory: |
      address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
      10.202.4.202,,2c,public,,,2000,,t,
```

Then if the device `sysDescr` match `'.*linux.*'` filter, `smart_profile` profile is enabled.


## varBinds configuration
`varBinds` short for "variable binding" in SNMP. The combination of an Object Identifier (OID) and a value. 
`varBinds` are used for defining in profiles what OIDs should be getting from SNMP Agents. `varBinds` is a required 
subsection of each profile. Syntax configuration of `varBinds` looks following:

 [ "MIB-Component", "MIB object"[Optional], "MIB index number"[Optional]]
 
 - `MIB-Component` - The SNMP MIB, itself, consists of distinct component MIBs, each of which refers to a specific 
 defined collection of management information that is part of the overall SNMP MIB eg. `SNMPv2-MIB`. 
 If only `MIB-Component` is set then all whole subtree is getting.
 - `MIB object` -  The SNMP MIB stores only simple data types: scalars and two-dimensional arrays of scalars, 
 called tables. Keywords SYNTAX, ACCESS, and DESCRIPTION as well as other keywords such as STATUS and 
 INDEX is used to define the SNMP MIB managed objects. 
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
Static Profile are used when they are defined on a list of profiles in inventory configuration in `poller` 
service [Inventory configuration](../poller-configuration/#configure-inventory). Static Profiles are executed 
even if the SmartProfile flag in inventory is set to false. 
To configure Static Profile following value needs to be set in `profiles` section:

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

Sometimes static profiles have additional functionalities, to be used in some special scenarios. 

#### WALK profile

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
Such profile should be placed in the profiles section of inventory definition. It will be executed with the frequency defined in `walk_interval`.
In case of multiple profiles of type `walk` will be placed in profiles, the last one will be used. 

This is how to use `walk` profiles:

```yaml
poller:
  inventory: |
    address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
    10.202.4.202,,2c,public,,,2000,small_walk,,
```

NOTE: When small walk is configured, you can set up polling only of OIDs belonging to walk profile varBinds. 
Additionally, there are two MIB families that are enabled by default (we need them to create state of the device in the database and poll base profiles): `IF-MIB` and `SNMPv2-MIB`.
For example, if you've decided to use `small_walk` from the example above, you'll be able to poll only `UDP-MIB`, `IF-MIB` and `SNMPv2-MIB` OIDs.


## SmartProfile configuration
SmartProfile is executed when the SmartProfile flag in inventory is set to true and the condition defined in profile match. 
More information about configuring inventory can be found in [Inventory configuration](../poller-configuration/#configure-inventory)

To configure Smart Profile following value need to be set in `profiles` section:

 - `ProfileName` - define as subsection key in `profiles`. 
    - `frequency` - define an interval between executing SNMP gets in second.
    - `condition` - section define conditions to much profile
        - `type` - key of `condition` section which defines type of condition. Allowed value `base` and `field`. 
            - `base` type of condition will be executed when `SmartProfile` in inventory is set to true.
            - `field` type of condition will be executed if match `pattern` for defined `field`. Supported fields:
                -  "SNMPv2-MIB.sysDescr"
                -  "SNMPv2-MIB.sysObjectID"
        - `field` Define field name for condition type field. 
        - `pattern` Define list of regular expression pattern for MIB object field defined in `field` section. For example:
                - ".*linux.*"
    - `varBinds` - define var binds to query. 

Example of `base` type of condition
```yaml
scheduler:
    profiles: |
      SmartProfile_base_example:
        frequency: 10
        condition: 
          type: "base"
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
          type: "field"
          field: "SNMPv2-MIB.sysDescr"
          patterns:
            - '.*STRING_TO_BE_MATCHED.*'
        varBinds:
          - ['SNMPv2-MIB']
          - ['SNMPv2-MIB', 'sysName']
``` 

NOTE: Be aware that profile changes may not be reflected immediately. It can take up to 5 minutes for changes to propagate. 
There is also 5 minute TTL for an inventory pod. Basically, SC4SNMP allows one inventory upgrade and then block updates for the next 5 minutes

## Custom translations
If the user wants to use custom names/translations of MIB names, it can be configured under customTranslations section under scheduler config.
Translations are grouped by MIB family. In the example below IF-MIB.ifInDiscards will be translated to IF-MIB.myCustomName1
```yaml
scheduler:
    customTranslations:
      IF-MIB:
        ifInDiscards: myCustomName1
        ifOutErrors: myCustomName2
      SNMPv2-MIB:
        sysDescr: myCustomName3
```

