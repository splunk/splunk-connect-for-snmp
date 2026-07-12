# Discovery Configuration

The discovery feature automatically discovers SNMP-enabled devices within a given subnet. Based on the discovery results, a `discovery_devices.csv` is generated and can be used to configure polling.

Discovery supports IPv4 and IPv6 subnets, SNMP v1, v2c, and v3 devices, and basic grouping of devices using SNMP `sysDescr` from `SNMPv2-MIB` (OID `1.3.6.1.2.1.1.1.0`).

## Enable Discovery

/// tab | microk8s
Set `discovery.enabled` to `true` in `values.yaml`:

```yaml
discovery:
  enabled: true
```

To apply changes, run the upgrade command:

```shell
microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
```
///

/// tab | docker compose
Set `COMPOSE_PROFILES=discovery` in your `.env` file. This starts the `discovery` and `worker-discovery` containers:

```
COMPOSE_PROFILES=discovery
```

To apply changes, recreate the containers:

```shell
sudo docker compose up -d
```
///

## Configuration overview

/// tab | microk8s
All discovery settings are configured in the `discovery` section of `values.yaml`:

```yaml
discovery:
  enabled:
  logLevel:
  subnetCheckConcurrency:
  ipv6Enabled:
  discoveryPath:
  usernameSecrets: []
  autodiscovery:
    discovery_key:
      frequency:
      delete_already_discovered:
      network_address:
      version:
      community:
      port:
      device_rules:
        - name:
          patterns:
          group:
```

### Example

```yaml
discovery:
  enabled: true
  logLevel: "INFO"
  subnetCheckConcurrency: 10
  ipv6Enabled: true
  discoveryPath: "/home/user/sc4snmp"
  usernameSecrets:
    - sc4snmp-hlab-sha-aes

  autodiscovery:
    discovery_version2c:
      frequency: 86400
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
///

/// tab | docker compose
Discovery settings are split across two files:

- **`.env`** — general settings: log level, output path, SNMPv3 secrets toggle, and subnet check concurrency.
- **`discovery-config.yaml`** — autodiscovery tasks. Set `DISCOVERY_CONFIG_FILE_ABSOLUTE_PATH` in `.env` to the absolute path of this file.

```yaml
ipv6Enabled:
autodiscovery:
  discovery_key:
    frequency:
    delete_already_discovered:
    network_address:
    version:
    community:
    port:
    device_rules:
      - name:
        patterns:
        group:
```

### Example `discovery-config.yaml`:

```yaml
ipv6Enabled: true
autodiscovery:
  discovery_version2c:
    frequency: 86400
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
///

## Define log level

Allowed values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`, `FATAL`. Default: `INFO`.

/// tab | microk8s
```yaml
discovery:
  logLevel: "INFO"
```
///

/// tab | docker compose
```
DISCOVERY_LOG_LEVEL=INFO
```
///

## Enable IPv6

Set `ipv6Enabled` to `true` to enable IPv6 subnet scanning.

/// tab | microk8s
```yaml
discovery:
  ipv6Enabled: true
```
///

/// tab | docker compose
In `discovery-config.yaml`:

```yaml
ipv6Enabled: true
```
///

!!! info
    If `ipv6Enabled` is `false`, then the task will not be created for discovery keys with an IPv6 network address.

## Define subnet check concurrency

Controls how many subnet IPs are checked concurrently inside one discovery task. Increase it to check large subnets faster, or lower it to reduce SNMP traffic, memory usage, and load on the discovery worker.

/// tab | microk8s
```yaml
discovery:
  subnetCheckConcurrency: 10
```
///

/// tab | docker compose
```
DISCOVERY_SUBNET_CHECK_CONCURRENCY=10
```
///

!!! info
    This setting is separate from `worker.discovery.concurrency` in microk8s and `WORKER_DISCOVERY_CONCURRENCY` in docker compose. Those settings control Celery worker task concurrency.

## Define discovery path

Specifies the absolute path where `discovery_devices.csv` will be created. If the file is not already present, a new one will be created.

/// tab | microk8s
```yaml
discovery:
  discoveryPath: "/home/user/sc4snmp"
```
///

/// tab | docker compose
```
DISCOVERY_PATH=/your/local/folder/path
```
///

!!! info
    The path provided should have read-write permission for user and group `10001`.

## Define SNMPv3 secrets

/// tab | microk8s
The `usernameSecrets` key defines which Kubernetes Secret objects are used for SNMPv3 discovery. The value must be the name of a Secret object.

```yaml
discovery:
  usernameSecrets:
    - sc4snmp-homesecure-sha-aes
    - sc4snmp-homesecure-sha-des
```
///

/// tab | docker compose
Set `ENABLE_WORKER_DISCOVERY_SECRETS=true` in `.env` to enable SNMPv3 secrets for the discovery worker, and ensure your secrets are configured in `secrets.json`.

```
ENABLE_WORKER_DISCOVERY_SECRETS=true
```
///

For more information on how to define secrets, see [SNMPv3 Configuration](snmpv3.md).

## Configure discovery tasks

Discovery tasks are defined under the `autodiscovery` section. Each task can target a specific subnet with its own SNMP version, credentials, and grouping logic. The discovery key (task name) must start with a letter (not a number).

Each task supports the following fields:

| Field                       | Description                                                                                                           | Default | Required |
|-----------------------------|-----------------------------------------------------------------------------------------------------------------------|---------|----------|
| `frequency`                 | Time interval (in seconds) between each run of the discovery task. If set to less than 6 hours, 6 hours will be used. | `86400` | NO       |
| `delete_already_discovered` | Deletes entries from the previous run under the same discovery key before writing new ones.                           | `false` | NO       |
| `network_address`           | Subnet in CIDR notation to scan. Supports IPv4 or IPv6.                                                               |         | YES      |
| `port`                      | SNMP listening port.                                                                                                  | `161`   | NO       |
| `version`                   | SNMP version. Allowed values: `1`, `2c`, `3`.                                                                         | `2c`    | NO       |
| `community`                 | SNMP community string. Required when `version` is `1` or `2c`.                                                        |         | NO       |
| `secret`                    | Reference to the SNMPv3 secret to use for discovery. Required when `version` is `3`.                                  |         | NO       |
| `security_engine`           | SNMPv3 security engine ID. If not provided for version `3`, it will be autogenerated.                                 |         | NO       |

### Define delete_already_discovered

The `delete_already_discovered` flag controls whether devices found in previous discovery runs are kept:

- If set to `true`, all devices discovered in the previous run under the same discovery key will be deleted. This ensures the list always reflects the most up-to-date set of devices.
- If set to `false`, devices from earlier runs are retained and new devices are appended. This is useful when you want a cumulative list of all SNMP-enabled devices discovered over time.

### Define device_rules

The `device_rules` section organizes discovered devices into logical groups based on pattern matching against their SNMP system description (`sysDescr`).

Each rule consists of:

- `name`: A label to identify the rule. Should be unique within the list.
- `patterns`: A wildcard pattern (supports `*`) matched against the `sysDescr` returned from SNMP.
- `group`: The name of the group to assign matched devices to.

```yaml
device_rules:
  - name: "Linux Devices"
    patterns: "*Linux*"
    group: "linux-group"
```

## Configure subnet check limits, timeouts, and retries

/// tab | microk8s
```yaml
discovery:
  subnetCheckConcurrency: 10

worker:
  taskTimeout: 2400
  udpConnectionTimeout: 3
  udpConnectionRetries: 5
```
///

/// tab | docker compose
```
DISCOVERY_SUBNET_CHECK_CONCURRENCY=10
CELERY_TASK_TIMEOUT=2400
UDP_CONNECTION_TIMEOUT=3
UDP_CONNECTION_RETRIES=5
```
///

| Field | microk8s | docker compose | Description | Default |
|-------|----------|----------------|-------------|---------|
| Subnet check concurrency | `discovery.subnetCheckConcurrency` | `DISCOVERY_SUBNET_CHECK_CONCURRENCY` | Number of subnet IPs checked concurrently inside one discovery task. This controls per-task subnet checking, not Celery worker task concurrency. | `10` |
| Task timeout | `worker.taskTimeout` | `CELERY_TASK_TIMEOUT` | Maximum execution time in seconds for a single discovery task. Increase for large subnets. Make sure it is large enough to accommodate SNMP checks across all IPs. | `2400` |
| UDP timeout | `worker.udpConnectionTimeout` | `UDP_CONNECTION_TIMEOUT` | Timeout in seconds for each SNMP request. Increase for high-latency networks. | `3` |
| UDP retries | `worker.udpConnectionRetries` | `UDP_CONNECTION_RETRIES` | Number of times a request is retried if there is no response. | `5` |

## Troubleshooting

For common issues such as permission errors, tasks exceeding the time limit, or no output in `discovery_devices.csv`, see [Discovery issues](../troubleshooting/discovery-issues.md).