# Discovery Configuration

The discovery feature automatically discovers SNMP-enabled devices within a given subnet. Based on the discovery results, a `discovery_devices.csv` is generated and can be used to configure polling.

Discovery supports IPv4 and IPv6 subnets, SNMP v1, v2c, and v3 devices, and basic grouping of devices using SNMP `sysDescr` from `SNMPv2-MIB` (OID `1.3.6.1.2.1.1.1.0`).


### Discovery configuration file

The discovery configuration is kept in the `values.yaml` file in the discovery section.
`values.yaml` is used during the installation process for configuring Kubernetes values.

See the following discovery example configuration:
```yaml
discovery:
  enabled: true
  logLevel: "DEBUG"
  ipv6Enabled: true
  discoveryPath: "/home/user/sc4snmp"
  usernameSecrets:
    - sc4snmp-hlab-sha-aes

  autodiscovery:
    discovery_version2c:
      frequency: 86400
      skip_active_check: false
      delete_already_discovered: true
      network_address: 10.202.4.200/30
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
      network_address: 10.202.4.200/30
      version: "3"
      port: 161
      secret: sc4snmp-hlab-sha-aes
      security_engine: "80001f8880e761866965756b6800000000"
      device_rules:
        - name: "Windows servers"
          patterns: "*Windows*"
          group: "windows-group"

```

### Enable Discovery
To enable or disable the discovery feature set `enabled` key. 
The default value is `false`. 

### Define log level
The log level for discovery can be set by changing the value for the `logLevel` key. The allowed values are`DEBUG`, `INFO`, `WARNING`, or `ERROR`. 
The default value is `WARNING`.

### Enable IPv6
To enable IPv6 subnet scanning, set `ipv6Enabled` key.

!!! info 
    If `ipv6Enabled` is `false`, then the task will not be created for discovery key with IPv6 network address.

### Define Discovery Path
`discoveryPath` specifies the absolute path on the local file system where the `discovery_devices.csv` file will be created.
If the CSV file is not already present, then a new file will be created.

!!! info
    The path provided should have read-write permission for user and group `10001`.

### Define usernamesecrets
The `usernameSecrets` key in the `discovery` section defines the SNMPv3 secrets for the discovery of the SNMP device. 
`usernameSecrets` defines which secrets in "Secret" objects in k8s should be used, as a value, it needs the name of "Secret" objects. 
For more information on how to define the "Secret" object for SNMPv3, see [SNMPv3 Configuration](snmpv3-configuration.md).

See the following example:
```yaml
discovery:
    usernameSecrets:
      - sc4snmp-homesecure-sha-aes
      - sc4snmp-homesecure-sha-des
```   

### Configure discovery tasks
Discovery tasks are defined under the autodiscovery section. Each discovery task can target a specific subnet with its own SNMP version and settings. 
Discovery key (i.e. task name) must start with a letter (not a number).

Each task has the following fields to configure:

| Field                          | Description                                                                                                                                                                                                                             | Default | Required |
|------------------              |-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------|----------|
| `frequency`                    | Time interval (in minutes) between each run of the discovery task. Note: If the frequency is less than 6 hours, it will be taken as 6 hours by default.                                                                                                                                                                        | `86400` | NO       |
| `skip_active_check`            | Skips the namp check and assumes all IPs are active.                                                                                                                                                                                          | `false` | NO       |
| `delete_already_discovered`    | Deletes old entries of a particular discovery key before writing new ones.                                                                                                                                                              | `false` | NO       |
| `network_address`              | Subnet in CIDR notation to scan. Supports IPv4 or IPv6.                                                                                                                                                                                 |         | YES      |
| `port`                         | SNMP listening port.                                                                                                                                                                                                                    | `161`   | NO       |
| `version`                      | SNMP version, the allowed values are `1`, `2c`, or `3`.                                                                                                                                                                                 |    `2c`     | NO      |
| `community`                    | SNMP community string, this field is required when the `version` is `1` or `2c`.                                                                                                                                                        |         | NO       |
| `secret`                       | The reference to the secret from `discovery.usernameSecrets` that should be used to discover, this field is required when the `version` is `3` devices.                                                                                                                                   |         | NO       |
| `security_engine`              | The security engine ID required by SNMPv3. If it is not provided for version `3`, it will be autogenerated.                                                                                                                             |         | NO       |

### Define skip_active_check
If set to `true`, SC4SNMP will skip the check for active devices using Nmap and process all IPs in the subnet directly.  
If `false`, it will first use Nmap to find active devices and then proceed only with those IPs.

### Define delete_already_discovered
The `delete_already_discovered` flag controls whether devices found in previous discovery runs are kept.

Since the discovery task runs at fixed intervals to scan for SNMP-enabled devices:
  - If set to `true`, all devices discovered in the previous run under the same discovery key will be deleted. This is useful when you want to ensure that the list always reflects the most up-to-date set of devices.
  - If set to `false`, it will retain devices discovered in earlier runs, and new devices will be appended to the existing list. This is useful when you want to keep a cumulative list of all SNMP-enabled devices discovered over time.

### Define device_rules
The `device_rules` section is used to organize discovered devices into logical groups based on pattern matching against their SNMP system descriptions (sysDescr).

Each rule consists of:

- `name`: A label to identify the rule. It is used for reference and should be unique within the list.
- `patterns`: A wildcard pattern (supports `*`) that matches against the `sysDescr` returned from SNMP.
- `group`: The name of the group to assign the matched devices to. This group can later be referenced for polling or other configurations.

**Example**
```yaml
device_rules:
  - name: "Linux Devices"
    patterns: "*Linux*"
    group: "linux-group" 
```

### Configure Timeouts and Retries

**Example**
```yaml
worker:
  taskTimeout: 8000
  udpConnectionTimeout: 3
  udpConnectionRetries: 5 
```

The following fields help control how long discovery tasks run and how SNMP responses are handled, especially for slower networks or larger subnets:

#### `taskTimeout`

Defines the **maximum execution time (in seconds)** for a single discovery task.  
- Default: `2400` seconds.  
- Increase this if you are scanning large subnets or using longer SNMP retry configurations.

Make sure `taskTimeout` is large enough to accommodate the `nmap` scan and the SNMP checks across all IPs.

#### `udpConnectionTimeout`

Specifies the **timeout (in seconds)** for each SNMP request (`getCmd`).  
Increase this if devices take longer to respond or if there is network latency.

#### `udpConnectionRetries`

Determines how many times a request is retried if there is no response.  
Higher retries can improve success rates on unstable networks, but will increase total execution time.
