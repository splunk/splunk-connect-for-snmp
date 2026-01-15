
Traps configuration is stored in the `traps-config.yaml` file. This file has the following sections:

```yaml
communities:
  2c:
    - public
usernameSecrets: []
```

- `communities`: communities used for version `1` and `2c` of the snmp. The default one is `public`.
- `usernameSecrets`: names of the secrets configured in docker used for `snmpv3` traps. 

## Example of the configuration

```yaml
communities:
  2c:
    - public
usernameSecrets: 
  - my_secret
```

## Prerequisites for SNMPv3 Configuration

### Create the SNMPv3 Secret in Docker
Before using SNMPv3, you must create the required secret within Docker. For detailed instructions, refer to [SNMPv3 secrets](7-snmpv3-secrets.md).

### Configure the Security Engine ID
To enable SNMPv3 functionality, the Security Engine ID must be specified. Please follow the guidelines in the 
[Traps Section of the .env File Configuration](6-env-file-configuration.md#traps) for instructions on setting this value.

