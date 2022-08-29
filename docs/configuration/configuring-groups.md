# Configuring Groups

It is common to configure whole groups of devices instead of just single ones. 
SC4SNMP allows both types of configuration. Group consists of many hosts. Each of them is configured in `values.yaml` 
file in the `scheduler` section. After configuring a group, it's name can be used in the `address`
field in the inventory record. All settings specified in the inventory record will be assigned to hosts from the given group, 
unless specific host configuration overrides it.

- Group configuration example can be found on [Scheduler Configuration](scheduler-configuration.md#define-groups-of-hosts) page.
- Use of groups in the inventory can be found on [Poller Configuration](poller-configuration.md#configure-inventory) page.

