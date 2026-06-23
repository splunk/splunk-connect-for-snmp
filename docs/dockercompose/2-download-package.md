# Download package with docker compose files

## Downloading a package
Package with docker compose configuration files (`docker_compose.zip`) can be downloaded from the [Github release](https://github.com/splunk/splunk-connect-for-snmp/releases).

## Configuration files

After extracting the package, you need to create or edit the following files before running `docker compose up`:

| File | Purpose | Details |
|------|---------|---------|
| Inventory file | Defines which devices to poll | [Inventory configuration](./3-inventory-configuration.md) |
| Scheduler config file | Defines polling profiles, communities, and groups | [Scheduler configuration](./4-scheduler-configuration.md) |
| Traps config file | Defines communities and secrets for receiving traps | [Traps configuration](./5-traps-configuration.md) |
| `secrets.json` | Stores SNMPv3 credentials (optional, SNMPv3 only) | [SNMPv3 secrets](../configuration/snmpv3.md) |
| `.env` | Sets absolute paths to the files above, Splunk connection details, and tuning parameters | [.env file](./6-env-file-configuration.md) |

!!! note
    The inventory, scheduler, and traps files can be named and placed anywhere on the host. What matters is that their absolute paths are correctly set in `.env` via `INVENTORY_FILE_ABSOLUTE_PATH`, `SCHEDULER_CONFIG_FILE_ABSOLUTE_PATH`, and `TRAPS_CONFIG_FILE_ABSOLUTE_PATH`. A default `Corefile` is shipped inside the `docker_compose` package - its absolute path must be set via `COREFILE_ABS_PATH`. The `secrets.json` filename is fixed - only the folder path is configurable via `SECRET_FOLDER_PATH`.

Work through each page in order. Once all files are ready, proceed to [Deploy the app](./11-deploy-and-run.md).

## Quick start example

The following is a minimal, working configuration for polling a single SNMPv2c device. Use it as a starting point and adapt it to your environment.

**Inventory file** - one device at `192.168.1.1`, with a minimal SNMPv2-MIB walk every 1800 seconds and profile-based polling every 300 seconds (as defined by `simple_profile` below), using SNMPv2c community `public`:

```csv
address,port,version,community,secret,securityEngine,walk_interval,profiles,smart_profiles,max_oid_to_process,delete
192.168.1.1,161,2c,public,,,1800,simple_profile,t,,
```

**Scheduler config file** - define the `public` community and the `simple_profile` profile referenced above:

```yaml
communities:
  2c:
    - public
profiles:
  simple_profile:
    frequency: 300
    varBinds:
      - [ 'IF-MIB' ]
      - [ 'SNMPv2-MIB' ]
```

**Traps config file** - accept traps from SNMPv2c devices using the `public` community:

```yaml
communities:
  2c:
    - public
usernameSecrets: []
```

**`.env`** - set the required variables (adjust paths and Splunk details to your environment):

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
    The profile name used in the inventory file (`simple_profile`) must match a profile defined in the scheduler config file. If the name does not match, SC4SNMP will not poll the device.

!!! info "Default walk scope"
    By default, SC4SNMP only walks `SNMPv2-MIB`. To expand the walk scope, define a walk profile in the scheduler config file (see [Profiles configuration](../configuration/profiles.md#walk-profile)) or set `ENABLE_FULL_WALK=true` in `.env` to walk the full OID tree.