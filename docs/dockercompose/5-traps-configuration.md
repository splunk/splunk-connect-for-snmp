# Traps configuration

## .env reference

| `.env` variable | Description |
|---|---|
| `TRAPS_CONFIG_FILE_ABSOLUTE_PATH` | Absolute path to this file on the host |

!!! info "Full reference"
    For the complete configuration reference, see the [Traps configuration](../configuration/traps.md) page — open the **docker compose** tab.

## Configuration

```yaml
communities:
  1:
    - private
  2c:
    - public
    - switch
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

## Advanced configuration


### Create the SNMPv3 Secret in Docker
Before referencing a secret in `usernameSecrets`, you must create it in Docker first. Complete the [SNMPv3 secrets](../configuration/snmpv3.md) page, then return here and add the secret name to `usernameSecrets`.

### Configure the Security Engine ID

In SNMPv3, every trap receiver must know the Security Engine ID of each sending device in advance. The receiver uses this ID together with the USM username, auth key, and priv key to authenticate incoming traps. Without the correct engine ID pre-registered, pysnmp rejects the trap before it even checks credentials.

Set the engine IDs as a comma-separated list in `.env` using `SNMP_V3_SECURITY_ENGINE_ID`:

```
SNMP_V3_SECURITY_ENGINE_ID=80003a8c04,aab123456
```

See the [Traps section of the .env file](6-env-file-configuration.md#traps) for the full variable reference.

#### Engine ID Discovery
If you are managing a large amount of traps agents it is possible to enable engine id discovery mode. The Engine ID Discovery feature automatically extracts the engine ID from each incoming SNMPv3 raw datagram and dynamically registers it with the SNMP engine, so the trap can be authenticated on the fly.
The engine ID is only registered if the username matches a known user and stored in database.

This feature can be enabled by setting in `.env`: 

```
DISCOVER_ENGINE_ID=true
```

!!! info
    It is recommended to enable this feature only during the initial setup of the traps receiver. Once the engine IDs for all required devices in the network have been collected, disable the feature to prevent unwanted engine ID registration and to improve trap processing efficiency by eliminating the overhead of extracting the engine ID from every incoming message.