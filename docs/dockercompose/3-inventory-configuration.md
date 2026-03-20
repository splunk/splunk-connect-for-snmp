# Inventory configuration

Inventory configuration is stored in a CSV file whose absolute path is set via `INVENTORY_FILE_ABSOLUTE_PATH` in `.env`. Full field reference and configuration details can be found on the [Inventory configuration](../configuration/inventory.md) page — open the **docker compose** tab.

## Example of the configuration

```csv
address,port,version,community,secret,securityEngine,walk_interval,profiles,smart_profiles,delete
0.0.0.0,161,2c,public,,,1800,small_walk;test_profile,t,
my_group,161,3,,my_secret,,1800,single_metric,t,
```