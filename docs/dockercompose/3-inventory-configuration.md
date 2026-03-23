# Inventory configuration

## .env reference

| `.env` variable | Description |
|---|---|
| `INVENTORY_FILE_ABSOLUTE_PATH` | Absolute path to this file on the host |

!!! info "Full reference"
    For the complete field reference and advanced configuration options, see the [Inventory configuration](../configuration/inventory.md) page — open the **docker compose** tab.

## Example of the configuration

!!! note
    The `profiles` values in the inventory (e.g. `small_walk`, `test_profile`, `single_metric`) must match profile names defined in the [scheduler config file](4-scheduler-configuration.md). If a profile name does not match, SC4SNMP will not poll that device.

```csv
address,port,version,community,secret,securityEngine,walk_interval,profiles,smart_profiles,delete
192.168.1.1,161,2c,public,,,1800,small_walk;test_profile,t,
my_group,161,3,,my_secret,,1800,single_metric,t,
```