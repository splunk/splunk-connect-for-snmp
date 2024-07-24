# Download package with docker compose files

## Downloading a package
Package with docker compose configuration files (`docker_compose.zip`) can be downloaded from the [Github release](https://github.com/splunk/splunk-connect-for-snmp/releases).

## Configuration
To configure the deployment, follow the instructions in [Inventory configuration](./3-inventory-configuration.md), 
[Scheduler configuration](./4-scheduler-configuration.md), [Traps configuration](./5-traps-configuration.md),
[.env file configuration](./6-env-file-configuration.md), [SNMPv3 secrets](./7-snmpv3-secrets.md)

## Deploying the app
After configuration, application can be deployed by running the
following command inside the `docker_compose` directory:

```shell
sudo docker compose $(find docker* | sed -e 's/^/-f /') up -d
```

The same command can be run to apply any updated configuration changes.

## Uninstall the app

To uninstall the app, run the following command inside the `docker_compose` directory:

```shell
sudo docker compose $(find docker* | sed -e 's/^/-f /') down
```