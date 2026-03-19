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

## Uninstall the app

To uninstall the app, run the following command inside the `docker_compose` directory:

```shell
sudo docker compose down
```
