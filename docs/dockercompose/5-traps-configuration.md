
Traps configuration is stored in the `traps-config.yaml` file. This file has the following sections:

```yaml
communities:
  2c:
    public:
      communityIndex:
      contextEngineId:
      contextName:
      tag:
      securityName:
usernameSecrets: []
```

- `communities`: communities used for version `1` and `2c` of the snmp. The default one is `public`.
- `usernameSecrets`: names of the secrets configured in docker used for `snmp v3` traps .

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
usernameSecrets: 
  - my_secret
```