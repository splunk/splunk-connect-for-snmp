# Docker logging

SC4SNMP applications write logs to container standard output and standard error. Docker controls how those container logs are stored and retained. These settings do not change SC4SNMP log levels, messages, formats, or destinations.

The default Compose configuration uses the `json-file` driver with bounded rotation for every service:

```dotenv
DOCKER_LOG_DRIVER=json-file
DOCKER_LOG_MAX_SIZE=10m
DOCKER_LOG_MAX_FILE=5
DOCKER_LOG_COMPRESS=true
```

Docker applies logging-driver changes when containers are created. Run `docker compose up -d` after changing the logging configuration so Compose can recreate the affected containers.

## Choose the logging behavior

Check the Docker daemon's current logging driver before a new installation or upgrade:

```shell
sudo docker info --format '{{.LoggingDriver}}'
```

| Desired behavior | Value in `.env` | Result after running `--configure_default_logging` |
|------------------|-----------------|----------------------------------------------------|
| Use bounded `json-file` logging | `DOCKER_LOG_DRIVER=json-file` | Compose applies `json-file` with the configured rotation limits |
| Keep the Docker daemon's current driver | Use the value reported by `docker info` | Compose logging is removed and containers inherit the daemon driver |
| Explicitly inherit the daemon driver | `DOCKER_LOG_DRIVER=inherit` | Compose logging is removed and containers inherit the daemon driver |
| Use the SC4SNMP default | Leave the variable missing or empty | Compose applies bounded `json-file` logging |

`DOCKER_LOG_DRIVER` is a selector used by `manage_logs.py`. It does not directly set a non-JSON driver on each service. For example, `DOCKER_LOG_DRIVER=local` makes containers use `local` only when `local` is the Docker daemon default.

## Keep the current driver during an upgrade

If `docker info` reports `local`, add or update this line in `.env` file:

```dotenv
DOCKER_LOG_DRIVER=local
```

Use the exact value reported by `docker info` when preserving another driver. Before starting the upgraded deployment, run:

```shell
cd /home/ubuntu/docker_compose
python3 manage_logs.py \
  --path_to_compose /home/ubuntu/docker_compose \
  --configure_default_logging
sudo docker compose config --quiet
sudo docker compose up -d
```

The helper removes service-level logging for non-JSON values, allowing the upgraded containers to continue using the Docker daemon driver. If this step is skipped, new or recreated SC4SNMP containers use bounded `json-file` logging.

## Switch to bounded `json-file`

To switch from any current logging driver to bounded `json-file`, set these values in `.env`:

```dotenv
DOCKER_LOG_DRIVER=json-file
DOCKER_LOG_MAX_SIZE=10m
DOCKER_LOG_MAX_FILE=5
DOCKER_LOG_COMPRESS=true
```

Apply the configuration:

```shell
cd /home/ubuntu/docker_compose
python3 manage_logs.py \
  --path_to_compose /home/ubuntu/docker_compose \
  --configure_default_logging
sudo docker compose config --quiet
sudo docker compose up -d
```

This changes logging only for the SC4SNMP Compose services. It does not change the Docker daemon or unrelated containers. Named MongoDB and Redis volumes are preserved by `docker compose up -d`. Do not use `docker compose down -v` for this change.

## Verify the effective configuration

After the containers are recreated, check their logging drivers and options:

```shell
for id in $(sudo docker compose ps -q)
do
  sudo docker inspect \
    --format '{{.Name}} driver={{.HostConfig.LogConfig.Type}} options={{json .HostConfig.LogConfig.Config}}' \
    "$id"
done
```

Bounded logging reports `driver=json-file` with `max-size`, `max-file`, and `compress`. When daemon inheritance is selected, each container reports the daemon driver.

## Restore Docker daemon inheritance directly

The following command removes service-level logging without reading `DOCKER_LOG_DRIVER`:

```shell
python3 manage_logs.py \
  --path_to_compose /home/ubuntu/docker_compose \
  --use_docker_default_logging
sudo docker compose up -d
```

This also removes the SC4SNMP service-level retention limits. If the daemon uses `json-file` without daemon-level `max-size` and `max-file` options, its container logs do not have a configured size limit. Check `/etc/docker/daemon.json` before selecting daemon inheritance.

To send Docker container logs to Splunk instead, see [Sending logs to Splunk](./9-splunk-logging.md).
