# Discovery configuration

Discovery configuration is stored in the `discovery-config.yaml` file. This file has the following sections:

```yaml
enabled: 
ipv6Enabled: 
autodiscovery:
  discovery_key:
      frequency: 
      skip_active_check: 
      delete_already_discovered: 
      network_address: 
      version: 
      community: 
      port: 
      device_rules:
        - name: 
          patterns: 
          Group: 

```

- `enabled`: To enable or disable the discovery feature set `enabled` key. The default value is `false`. 
- `ipv6Enabled`: To enable IPv6 subnet scanning set `ipv6Enabled` key.

!!! info 
    If `ipv6Enabled` is `false`, then the task will not be created for discovery key with IPv6 network address.

- `autodiscovery`: Discovery tasks are defined under the autodiscovery section. Each task can target a specific subnet with its own SNMP version and settings. 
Task name must start with a letter (not a number). Configuration of this section looks the same as in the `values.yaml` in `discovery.autodiscovery` section, which can be checked in the documentation of [discovery configuration](../microk8s/configuration/discovery-configuration.md).

## Example of the configuration

```yaml
enabled: true
ipv6Enabled: true
autodiscovery:
  discovery_version2c:
    frequency: 86400
    skip_active_check: false
    delete_already_discovered: true
    network_address: 10.202.4.202/30
    version: "2c"
    community: "public"
    port: 161
    device_rules:
    - name: "Linux servers"
        patterns: "*linux*"
        group: "linux-group"

  discovery_version3:
    frequency: 43200
    skip_active_check: false
    delete_already_discovered: false
    network_address: 10.202.4.202/30
    version: "3"
    port: 161
    secret: sc4snmp-hlab-sha-aes
    security_engine: "80001f8880e761866965756b6800000000"
    device_rules:
      - name: "Windows servers"
        patterns: "*Windows*"
        group: "windows-group"

```
