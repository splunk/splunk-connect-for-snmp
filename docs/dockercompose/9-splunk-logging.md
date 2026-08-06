# Sending logs to Splunk

The default Docker Compose configuration does not forward container logs to Splunk. SC4SNMP application logging remains enabled, and container logs can be accessed with:
```
docker logs <container_name/id>
```

Enabling Docker-to-Splunk forwarding requires updating the logging configuration of every service. To simplify this process, the `docker_compose` package includes `manage_logs.py`.

Docker applies logging-driver changes only when containers are created. Recreate the affected containers after enabling or disabling forwarding. For Docker log retention and daemon-driver inheritance, see [Docker logging](./7-docker-logging.md).

## Prerequisites

Running script requires installation of `ruamel.yaml` package for python. It can be done with command:
```
pip3 install ruamel.yaml
```

To enable Docker-to-Splunk forwarding, the following parameters have to be configured in `.env` file:
`SPLUNK_HEC_TOKEN`, `SPLUNK_HEC_PROTOCOL`, `SPLUNK_HEC_HOST`, `SPLUNK_HEC_PORT`, `SPLUNK_LOG_INDEX`, `SPLUNK_HEC_INSECURESSL`.

More about `.env` configuration can be found in [.env file configuration](./6-env-file-configuration.md).

## Enabling logging

To enable Docker-to-Splunk container-log forwarding, run `manage_logs.py` with:

| Flag                      | Description                                          |
|---------------------------|------------------------------------------------------| 
| `-e`, `--enable_logs`     | Enable Docker-to-Splunk container-log forwarding     |
| `-p`, `--path_to_compose` | Absolute path to directory with docker compose files |

Example of enabling logs:
```
python3 manage_logs.py \
  --path_to_compose /home/ubuntu/docker_compose \
  --enable_logs
```

The script sets the Splunk logging driver on every service and keeps `docker logs` available through Docker's bounded local dual-logging cache.
To apply the changes run the: 
```
sudo docker compose up -d
```
command inside the `docker_compose` directory.

## Disabling Docker to Splunk logs forwarding

To disable Docker-to-Splunk forwarding, run `manage_logs.py` with:

| Flag                      | Description                                          |
|---------------------------|------------------------------------------------------| 
| `-d`, `--disable_logs`    | Disable Docker-to-Splunk container-log forwarding    |
| `-p`, `--path_to_compose` | Absolute path to directory with docker compose files |

The script restores the bounded `json-file` driver. It does not disable SC4SNMP application logging or change log levels, messages, formats, or stdout/stderr behavior. To inherit the Docker daemon driver instead, follow the [Docker logging](./7-docker-logging.md#choose-the-logging-behavior) instructions after disabling forwarding.

Example of disabling logs:
```
python3 manage_logs.py \
  --path_to_compose /home/ubuntu/docker_compose \
  --disable_logs
```

To apply the changes run the:
```
sudo docker compose up -d
```
command inside the `docker_compose` directory.

After that the logs can be reached with `docker logs` command.
