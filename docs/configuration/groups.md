# Configuring groups

It is common to configure whole groups of devices instead of just single ones.
SC4SNMP allows both types of configuration. A group consists of many hosts. After configuring a group, its name can be used in the `address`
field in the inventory record. All settings specified in the inventory record will be assigned to hosts from the given group,
unless specific host configuration overrides it.

## Group vs host

If the host is configured in the group and both the group and the single host are included in the inventory, the
configuration for the single host will be ignored in favor of the group configuration. See the following example:

```yaml
groups:
  example_group_1:
    - address: 10.202.4.202
      port: 161
    - address: 63.2.40.0
      port: 161
```

```
address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,max_oid_to_process,delete
example_group_1,,2c,public,,,2000,my_profile2,,,
10.202.4.202,,2c,public,,,2000,my_profile1,,,
```

If the specific host from the group has to be configured separately, first it must be deleted from the group configuration,
and then it can be inserted as a new record in the inventory.

The one obligatory field for the host configuration is `address`. If `port` is not configured its default value is `161`.
Other fields that can be modified are: `community`, `secret`, `version`, `security_engine` and `max_oid_to_process`.
However, if they remain unspecified in the host configuration, they will be derived from the inventory record or default.

## Configuration

/// tab | microk8s
Groups are defined in the `scheduler.groups` section of `values.yaml`:

```yaml
scheduler:
  groups: |
    example_group_1:
      - address: 123.0.0.1
        port: 161
      - address: 178.8.8.1
        port: 999
      - address: 12.22.23
        port: 161
        community: 'private'
    example_group_2:
      - address: 103.0.0.1
        port: 1161
        version: '3'
        secret: 'my_secret'
      - address: 178.80.8.1
        port: 999
```

To apply changes, run the upgrade command:

```shell
microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
```
///

/// tab | docker compose
Groups are defined in the `groups` section of `scheduler-config.yaml`:

```yaml
groups:
  example_group_1:
    - address: 123.0.0.1
      port: 161
    - address: 178.8.8.1
      port: 999
    - address: 12.22.23
      port: 161
      community: 'private'
  example_group_2:
    - address: 103.0.0.1
      port: 1161
      version: '3'
      secret: 'my_secret'
    - address: 178.80.8.1
      port: 999
```

To apply changes, run the following command inside the `docker_compose` directory:

```shell
sudo docker compose up -d
```
///
