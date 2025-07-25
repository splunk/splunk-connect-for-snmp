# Download package with docker compose files

## Downloading a package
Package with docker compose configuration files (`docker_compose.zip`) can be downloaded from the [Github release](https://github.com/splunk/splunk-connect-for-snmp/releases).

## Configuration
To configure the deployment, follow the instructions in [Inventory configuration](./3-inventory-configuration.md), 
[Scheduler configuration](./4-scheduler-configuration.md), [Traps configuration](./5-traps-configuration.md),
[.env file configuration](./6-env-file-configuration.md), [SNMPv3 secrets](./7-snmpv3-secrets.md).


## Protect Mongo and Redis by password

In your `docker-compose.yaml` [specify](https://hub.docker.com/r/bitnami/redis) for Redis container `REDIS_PASSWORD` or `REDIS_PASSWORD_FILE`:

```
  redis:
  ...
    environment:
      - REDIS_PASSWORD=...
```

The same thing you to [specify](https://hub.docker.com/r/bitnami/mongodb) for Mongo container using `MONGODB_ROOT_PASSWORD`:

```
  mongo:
  ...
    environment:
      - MONGODB_ROOT_PASSWORD=...
```

After that just update connection string:

```
REDIS_URL: redis://:pass@redis:6379/1
CELERY_BROKER_URL: redis://:pass@redis:6379/0
MONGO_URI: mongodb://root:pass@mongo:27017/
```

!!! Warning
    If you wanna update the password you need to make it manually using `mongo` and `redis` cli.
    And only after that you need to update `REDIS_PASSWORD`/ `MONGODB_ROOT_PASSWORD` and connection strings.

## Deploying the app
After configuration, application can be deployed by running the
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
sudo docker compose  down
```