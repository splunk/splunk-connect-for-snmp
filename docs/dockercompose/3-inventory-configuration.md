# Inventory configuration

Inventory configuration is stored in the `inventory.csv` file. Structure of this file is the same as the one of the 
`poller.inventory` section in `values.yaml` file. Documentation of this section can be found in [configure inventory](../microk8s/configuration/poller-configuration.md#configure-inventory).

## Example of the configuration

```csv
address,port,version,community,secret,securityEngine,walk_interval,profiles,smart_profiles,delete
0.0.0.0,161,2c,public,,,1800,small_walk;test_profile,t,
my_group,161,3,,my_secret,,1800,single_metric,t,
```