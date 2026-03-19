# Download package with docker compose files

## Downloading a package
Package with docker compose configuration files (`docker_compose.zip`) can be downloaded from the [Github release](https://github.com/splunk/splunk-connect-for-snmp/releases).

## Configuration
To configure the deployment, follow the instructions in [.env file configuration](./6-env-file-configuration.md),
[Inventory configuration](./3-inventory-configuration.md),
[Scheduler configuration](./4-scheduler-configuration.md), [Traps configuration](./5-traps-configuration.md),
[SNMPv3 secrets](./7-snmpv3-secrets.md).

Once all configuration files are ready, proceed to [Deploy the app](./11-deploy-and-run.md).

## Quick start example

The following is a minimal, working configuration for polling a single SNMPv2c device. Use it as a starting point and adapt it to your environment.

**`inventory.csv`** — one device at `192.168.1.1`, polled every 300 seconds using the `simple_profile` profile:

```csv
address,port,version,community,secret,securityEngine,walk_interval,profiles,smart_profiles,delete
192.168.1.1,161,2c,public,,,1800,simple_profile,t,
```

**`scheduler-config.yaml`** — define the `public` community and the `simple_profile` profile referenced above:

```yaml
communities:
  2c:
    public:
      communityIndex:
      contextEngineId:
      contextName:
      tag:
      securityName:
profiles:
  simple_profile:
    frequency: 300
    varBinds:
      - [ 'IF-MIB' ]
      - [ 'SNMPv2-MIB' ]
```

**`traps-config.yaml`** — accept traps from SNMPv2c devices using the `public` community:

```yaml
communities:
  2c:
    - public
usernameSecrets: []
```

**`.env`** — set the required variables (adjust paths and Splunk details to your environment):

```
SCHEDULER_CONFIG_FILE_ABSOLUTE_PATH=/home/ubuntu/docker_compose/scheduler-config.yaml
TRAPS_CONFIG_FILE_ABSOLUTE_PATH=/home/ubuntu/docker_compose/traps-config.yaml
INVENTORY_FILE_ABSOLUTE_PATH=/home/ubuntu/docker_compose/inventory.csv
COREFILE_ABS_PATH=/home/ubuntu/docker_compose/Corefile

SPLUNK_HEC_HOST=splunk.example.com
SPLUNK_HEC_PROTOCOL=https
SPLUNK_HEC_PORT=8088
SPLUNK_HEC_TOKEN=your-hec-token-here
SPLUNK_HEC_INSECURESSL=false

SPLUNK_HEC_INDEX_EVENTS=netops
SPLUNK_HEC_INDEX_METRICS=netmetrics
```

!!! note
    The profile name used in `inventory.csv` (`simple_profile`) must match a profile defined in `scheduler-config.yaml`. If the name does not match, SC4SNMP will not poll the device.