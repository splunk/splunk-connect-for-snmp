# Logging

The default configuration of docker compose is not sending the logs to Splunk. Container logs can be accessed with command:
```
docker logs <container_name/id>
```

Creating logs requires updating configuration of several docker compose files. To simplify this process, inside the 
`docker_compose` package there is a `manage_logs.py` file which will automatically manage logs.

## Prerequisites

Running script requires installation of `ruamel.yaml` package for python. It can be done with command:
```
pip3 install ruamel.yaml
```

The following parameters have to be configured in `.env` file:
`SPLUNK_HEC_TOKEN`, `SPLUNK_HEC_PROTOCOL`, `SPLUNK_HEC_HOST`, `SPLUNK_HEC_PORT`, `SPLUNK_LOG_INDEX`, `SPLUNK_HEC_INSECURESSL`.

More about `.env` configuration can be found in [.env file configuration](./6-env-file-configuration.md).

## Enabling logging

To enable a logging `manage_logs.py` must be run with the following flags:

| Flag                      | Description                                          |
|---------------------------|------------------------------------------------------| 
| `-e`, `--enable_logs`     | Flag enabling the logs                               |
| `-p`, `--path_to_compose` | Absolute path to directory with docker compose files |

Example of enabling logs:
```
python3 manage_logs.py --path_to_compose /home/ubuntu/docker_compose --enable_logs
```

The script will add required configuration for logging under services in docker compose files.
To apply the changes run the
```
sudo docker compose $(find docker* | sed -e 's/^/-f /') up -d
```
command inside the `docker_compose` directory.

## Disabling the logs

To disable logs `manage_logs.py` must be run with the following flags:

| Flag                      | Description                                          |
|---------------------------|------------------------------------------------------| 
| `-d`, `--disable_logs`    | Flag disabling the logs                              |
| `-p`, `--path_to_compose` | Absolute path to directory with docker compose files |

Running the disable command will replace the `logging.driver` section with default docker driver `json-file`. 

Example of disabling logs:
```
python3 manage_logs.py --path_to_compose /home/ubuntu/docker_compose --disable_logs
```

To apply the changes run the 
```
sudo docker compose $(find docker* | sed -e 's/^/-f /') up -d
```
command inside the `docker_compose` directory.

After that the logs can be reached with `docker logs` command.
