# Configuring Groups

It is common to configure whole groups of devices instead of just single ones. 
SC4SNMP allows both types of configuration. A group consists of many hosts. Each of them is configured in the `values.yaml` 
file, in the `scheduler` section. After configuring a group, its name can be used in the `address`
field in the inventory record. All settings specified in the inventory record will be assigned to hosts from the given group, 
unless specific host configuration overrides it.

- See the [Scheduler Configuration](scheduler-configuration.md#define-groups-of-hosts) page for group examples and documentation. 
- See the [Poller Configuration](poller-configuration.md#configure-inventory) page for information about groups in the inventory. 

If the host is configured in the group and both the group and the single host are included in the inventory, the
configuration for the single host will be ignored in favor of the group configuration. See the following example: 

```yaml
scheduler:
  groups: |
    example_group_1:
      - address: 10.202.4.202
        port: 161
      - address: 63.2.40.0
        port: 161
```

```yaml
poller:
    inventory: |
      address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
      example_group_1,,2c,public,,,2000,my_profile2,,
      10.202.4.202,,2c,public,,,2000,my_profile1,,
```

If the specific host from the group has to be configured separately, first it must be deleted from the group configuration,
and then it can be inserted as a new record in the inventory. See the following example:

```yaml
scheduler:
  groups: |
    example_group_1:
      - address: 63.2.40.0
        port: 161
```

```yaml
poller:
    inventory: |
      address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
      example_group_1,,2c,public,,,2000,my_profile2,,
      10.202.4.202,,2c,public,,,2000,my_profile1,,
```
