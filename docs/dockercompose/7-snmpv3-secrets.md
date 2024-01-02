# SNMPv3 secrets

Creating a secret requires updating configuration of several docker compose files. To simplify this process, inside the 
`docker_compose` package there is a `manage_secrets.py` file which will automatically manage secrets.

## Creating a new secret

To create a new secret, `manage_secrets.py` must be run with the following flags:

| Flag                | Description                                                                    |
|---------------------|--------------------------------------------------------------------------------| 
| `--secret_name`     | New secret name                                                                |
| `--path_to_compose` | Absolute path to directory with docker compose files                           |
| `--worker_poller`   | \[OPTIONAL\] Add new secrets to worker poller. Default value is set to 'true'. |
| `--traps`           | \[OPTIONAL\] Add new secrets to traps server. Default value is set to 'true'.  |
| `--userName`        | SNMPv3 userName                                                                |
| `--privProtocol`    | SNMPv3 privProtocol                                                            |
| `--privKey`         | SNMPv3 privKey                                                                 |
| `--authProtocol`    | SNMPv3 authProtocol                                                            |
| `--authKey`         | SNMPv3 authKey                                                                 |
| `--contextEngineId` | \[OPTIONAL\] SNMPv3 engine id                                                  |  

 
This script, apart from updating configuration files, creates environmental variables with values of the secret at the 
end of the `.env` file in the `docker_compose` directory. To apply these secrets run the 
`sudo docker compose $(find docker* | sed -e 's/^/-f /') up -d` command inside the `docker_compose` directory. After running this command, plain text secrets 
from the `.env` file can be deleted. One important thing is that if any change in `.env` is made, these secrets must be
recreated ([delete](#deleting-a-secret) an existing secret and create it once again).

### Example of creating a secret:
```shell
python3 <path_to_manage_secrets.py> --path_to_compose <path_to_compose> \
--secret_name my_secret \
--userName r-wuser \
--privProtocol AES \
--privKey admin1234 \
--authProtocol SHA \
--authKey admin1234 \
--contextEngineId 090807060504037
```

Inside `docker_compose` directory run :

```shell
sudo docker compose $(find docker* | sed -e 's/^/-f /') up -d
```

Now, the following lines from the `.env` can be deleted:

```.env
my_secret_userName=r-wuser
my_secret_privProtocol=AES
my_secret_privKey=admin1234
my_secret_authProtocol=SHA
my_secret_authKey=admin1234
my_secret_contextEngineId=090807060504037
```

## Deleting a secret

To create a secret, `manage_secrets.py` must be run with the following flags:

| Flag                | Description                                          |
|---------------------|------------------------------------------------------| 
| `--secret_name`     | Secret name                                          |
| `--path_to_compose` | Absolute path to directory with docker compose files |
| `--delete`          | Set this flag to true to delete the secret           |

This will delete the secret with a given name from all docker compose files. Also, if this secret hasn't been deleted
from `.env` file, it will be also deleted from there.

### Example of deleting a secret:
```shell
python3 <path_to_manage_secrets.py> --path_to_compose <path_to_compose> \
--secret_name my_secret \
--delete true 
```