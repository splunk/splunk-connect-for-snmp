# Deploy the app

After completing all configuration steps, the application can be deployed by running the
following command inside the `docker_compose` directory:

```shell
sudo docker compose up -d
```

!!! info
    The installation process changed from version **1.12.1**. For lower version refer to the corresponding
    documentation.

The same command can be run to apply any updated configuration changes.

## Verify the deployment

After the containers start, check that all services are running:

```shell
sudo docker compose ps
```

All containers should show a `running` state.

!!! info
    On first startup, some containers may take a moment to become healthy while MongoDB and Redis initialize. If a container shows `restarting`, wait 30 seconds and run `docker compose ps` again before investigating.

If any container is not running, check its logs for errors:

```shell
sudo docker logs <container_name>
```

For common problems and solutions, refer to the [Troubleshooting](../troubleshooting/general-issues.md) section.

## Verify data in Splunk

Once all containers are running, confirm that data is reaching Splunk.

!!! note
    Replace `netops` and `netmetrics` below with the index names you configured via `SPLUNK_HEC_INDEX_EVENTS` and `SPLUNK_HEC_INDEX_METRICS` if you changed the defaults.

### Verify traps

To verify that trap events are being received, send a test trap from any Linux machine that has the `snmp` package installed (replace `<SC4SNMP_HOST_IP>` with the IP address of the host running SC4SNMP):

```shell
snmptrap -v2c -c public <SC4SNMP_HOST_IP> 123 1.3.6.1.2.1.1.4 1.3.6.1.2.1.1.4 s test
```

Then search in Splunk:

```
index="netops" sourcetype="sc4snmp:traps"
```

You should see one event per trap command sent.

### Verify polling

SC4SNMP must complete an SNMP walk on each device before polling data appears in Splunk. The walk runs automatically on first startup and then repeats every `walk_interval`. Depending on the size of the device, this may take a few minutes.

!!! info "Default walk scope"
    By default, SC4SNMP only walks `SNMPv2-MIB`. If you expect interface or other MIB data and see only limited results, define a walk profile in your scheduler config file (see [Profiles configuration](../configuration/profiles.md#walk-profile)) or set `ENABLE_FULL_WALK=true` in `.env`.

Once the walk completes, search in Splunk for polling events:

```
index="netops" sourcetype="sc4snmp:event"
```

And for metrics:

```
| mpreview index="netmetrics" | search sourcetype="sc4snmp:metric"
```

!!! info
    If no data appears after one full `walk_interval`, check the `worker-poller` logs for errors: `sudo docker logs <worker-poller-container-name>`. For common polling problems see the [Troubleshooting](../troubleshooting/polling-issues.md) section.

## Applying configuration changes

To apply any change to `.env`, `inventory.csv`, `scheduler-config.yaml`, or `traps-config.yaml`, run the same command from inside the `docker_compose` directory:

```shell
sudo docker compose up -d
```

Docker Compose will recreate only the containers affected by the change. Existing data in MongoDB is preserved. After running the command, verify the containers are still running:

```shell
sudo docker compose ps
```

!!! note
    After an inventory change, SC4SNMP schedules a new walk for any added or modified device. Data for that device will not appear in Splunk until the walk completes. Walk duration depends on the device size and the configured `walk_interval`.

If changes are not picked up the docker compose up can be run with flag `--force-recreate`.

## Uninstall the app

To uninstall the app, run the following command inside the `docker_compose` directory:

```shell
sudo docker compose down --volumes
```
