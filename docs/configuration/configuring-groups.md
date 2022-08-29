# Configuring groups

It is common to configure whole groups of devices instead of just single ones. 
SC4SNMP allows both types of configuration. Group consists of many hosts. Each of them is configured in `values.yaml` 
file in the `scheduler` section. After configuring a group, it's name can be used in the `address`
field in the inventory record.

Example group configuration:
```yaml
scheduler:
  groups:
    example_group_1:
      - address: 123.0.0.1
        port: 161
      - address: 178.8.8.1
        port: 999
      - address: 12.22.23
        port: 161
        community: private
    example_group_2:
      - address: 103.0.0.1
        port: 1161
        walk_interval: 2500
      - address: 178.80.8.1
        port: 999
```

Two obligatory fields for the host configuration are `address` and `port`. Rest of the
fields which are not specified in the host configuration will be derived from the inventory record regarding specific group.

Example poller configuration including single device and groups:
```yaml
poller:
  logLevel: "WARN"
  inventory: |
    address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
    10.202.4.202,,2c,public,,,2000,my_profile1,,
    example_group_1,,2c,public,,,2000,my_profile2,,
    example_group_2,,2c,public,,,2000,my_profile3,,
```
