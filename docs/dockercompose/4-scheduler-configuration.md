# Scheduler configuration

## .env reference

| `.env` variable | Description |
|---|---|
| `SCHEDULER_CONFIG_FILE_ABSOLUTE_PATH` | Absolute path to this file on the host |

!!! info "Full reference"
    For the complete reference on profile types, conditions, groups, and custom translations, see [Profiles configuration](../configuration/profiles.md) and [Groups configuration](../configuration/groups.md).
    For log level, see [Define log level](#define-log-level) below.

## Configuration

```yaml
communities:
  2c:
    - public
customTranslations:
profiles:
groups:
```

- `communities`: communities used for version `1` and `2c` of the `snmp`. The default one is `public`.
- `customTranslations`: custom name mappings for MIB fields. See [Profiles configuration — Custom translations](../configuration/profiles.md#custom-translations).
- `profiles`: polling profiles defining what OIDs to collect and how often. See [Profiles configuration](../configuration/profiles.md).
- `groups`: named groups of devices that can be referenced in the inventory. See [Groups configuration](../configuration/groups.md).

## Define log level

Set the log level for the scheduler container in `.env`:

```
SCHEDULER_LOG_LEVEL=INFO
```

The allowed values are `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`, or `FATAL`.

## Example of the configuration

```yaml
communities:
  2c:
    - public
customTranslations:
  IF-MIB:
    ifInDiscards: myCustomName1
    ifOutErrors: myCustomName2
  SNMPv2-MIB:
    sysDescr: myCustomName3
profiles:
  small_walk:
    condition:
      type: "walk"
    varBinds:
      - [ 'IP-MIB' ]
      - [ 'IF-MIB' ]
      - [ 'TCP-MIB' ]
      - [ 'UDP-MIB' ]
  multiple_conditions:
    frequency: 10
    conditions:
      - field: IF-MIB.ifIndex
        operation: "gt"
        value: 1
      - field: IF-MIB.ifDescr
        operation: "in"
        value:
          - "eth0"
          - "test value"
    varBinds:
      - [ 'IF-MIB', 'ifOutDiscards' ]
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
      max_oid_to_process: 3
```