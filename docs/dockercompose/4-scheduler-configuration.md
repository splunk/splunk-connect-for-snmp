# Scheduler configuration

Scheduler configuration is stored in a YAML file whose absolute path is set via `SCHEDULER_CONFIG_FILE_ABSOLUTE_PATH` in `.env`. This file has the following sections:

## Configuration

```yaml
communities:
  2c:
    public:
      communityIndex:
      contextEngineId:
      contextName:
      tag:
      securityName:
customTranslations:
profiles:
groups:
```

- `communities`: communities used for version `1` and `2c` of the `snmp`. The default one is `public`.
- `customTranslations`: custom name mappings for MIB fields. See [Profiles configuration — Custom translations](../configuration/profiles.md#custom-translations).
- `profiles`: polling profiles defining what OIDs to collect and how often. See [Profiles configuration](../configuration/profiles.md).
- `groups`: named groups of devices that can be referenced in the inventory. See [Groups configuration](../configuration/groups.md).

## Example of the configuration

```yaml
communities:
  2c:
    public:
      communityIndex:
      contextEngineId:
      contextName:
      tag:
      securityName:
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
  group1:
    - address: 18.116.10.255
      port: 1163
```
