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

## Uninstall the app

To uninstall the app, run the following command inside the `docker_compose` directory:

```shell
sudo docker compose down
```
