# Scheduler configuration

Scheduler configuration is stored in the `scheduler-config.yaml` file. This file has the following sections:

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
- `customTranslations`: configuration of the custom translations. Configuration of this section looks the same as in the `values.yaml` in `scheduler.customTranslations` section, which can be checked in the documentation of [custom translations](../microk8s/configuration/configuring-profiles.md#custom-translations).
- `profiles`: configuration of the profiles. Configuration of this section looks the same as in the `values.yaml` in `scheduler.profiles` section, which can be checked in the documentation of [profiles configuration](../microk8s/configuration/configuring-profiles.md).
- `groups`: configuration of the groups. Configuration of this section looks the same as in the `values.yaml` in `scheduler.groups` section, which can be checked in the documentation of [groups configuration](../microk8s/configuration/configuring-groups.md).

!!! note
    The `profiles`, `groups`, and `customTranslations` configuration syntax is shared between the Docker Compose and Microk8s deployment models. The linked pages above apply equally to Docker Compose users.

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
