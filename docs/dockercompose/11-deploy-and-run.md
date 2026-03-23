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

To verify that trap events are being received, send a test trap from any Linux machine that has `snmp-utils` installed (replace `<SC4SNMP_HOST_IP>` with the IP address of the host running SC4SNMP):

```shell
snmptrap -v2c -c public <SC4SNMP_HOST_IP> 123 1.3.6.1.2.1.1.4 1.3.6.1.2.1.1.4 s test
```

Then search in Splunk:

```
index="netops" sourcetype="sc4snmp:traps"
```

You should see one event per trap command sent.

### Verify polling

SC4SNMP must complete an SNMP walk on each device before polling data appears in Splunk. The walk runs automatically on first startup and then repeats every `walk_interval` seconds. Depending on the size of the device, this may take a few minutes.

Once the walk completes, search in Splunk for polling events:

```
index="netops" sourcetype="sc4snmp:event"
```

And for metrics:

```
| mpreview index="netmetrics" | search sourcetype="sc4snmp:metric"
```

!!! info
    If no data appears after one full `walk_interval`, check the worker-poller logs for errors: `sudo docker logs <worker-poller-container-name>`. For common polling problems see the [Troubleshooting](../troubleshooting/polling-issues.md) section.

## Uninstall the app

To uninstall the app, run the following command inside the `docker_compose` directory:

```shell
sudo docker compose down
```
