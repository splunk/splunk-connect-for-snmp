# SNMPv3 configuration

!!! info "SNMPv3 only"
    This page is only relevant if you are using **SNMPv3** authentication. If your devices use SNMPv2c or SNMPv1, you can skip this page entirely.

Configuration of SNMPv3, when supported by the monitored devices, is the most secure choice available
for authentication and data privacy.

/// tab | microk8s
Each set of credentials is stored as a Kubernetes Secret object and referenced by name in `values.yaml`.
This allows the secret to be created once — including automation by third-party password managers — then consumed without storing sensitive data in plain text.

```bash
# <secretname>=Arbitrary name of the secret often the same as the username or prefixed with "sc4snmp-"
# <namespace>=Namespace used to install sc4snmp
# <username>=the SNMPv3 Username
# <key>=key note must be at least 8 char long subject to target limitations
# <authProtocol>=One of SHA (SHA1) or MD5
# <privProtocol>=One of AES or DES
# Note MD5 and DES are considered insecure but must be supported for standards compliance
microk8s kubectl create -n <namespace> secret generic <secretname> \
  --from-literal=userName=<username> \
  --from-literal=authKey=<key> \
  --from-literal=privKey=<key> \
  --from-literal=authProtocol=<authProtocol> \
  --from-literal=privProtocol=<privProtocol>
```

Configured credentials can be used in poller and trap services. In service configuration, `secretname` needs to be provided.

For poller:
```yaml
poller:
  usernameSecrets:
    - sc4snmp-hlab-sha-aes
```

For traps:
```yaml
traps:
  usernameSecrets:
    - sc4snmp-homesecure-sha-aes
```
///

/// tab | docker compose
All SNMPv3 secrets are managed through a single `secrets.json` file stored in a folder on the host.

### Prerequisites

Create a folder to store the secrets file. Inside this folder, create a `secrets.json` file that contains all SNMPv3 secrets.

```json
{
  "secret_name": {
    "username": "user1",
    "privprotocol": "AES",
    "privkey": "privkey1",
    "authprotocol": "SHA",
    "authkey": "authkey1",
    "contextengineid": "engineid1"
  }
}
```

> **_NOTE:_** The name of json file should be secrets.json. Username, authprotocol and authkey are mandatory parameters.

### Configuration

In the `.env` file, set the path to the local folder containing the `secrets.json`:

```
SECRET_FOLDER_PATH=/absolute/path/to/secrets/folder
```

Secrets usage for worker-poller and worker-trap can be controlled by flags in `.env`:

```
ENABLE_TRAPS_SECRETS=true
ENABLE_WORKER_POLLER_SECRETS=true
```

### Creating a new secret

Add an entry to `secrets.json`, then inside the `docker_compose` directory run:

```shell
sudo docker compose up -d
```

### Updating existing secret

Update the required fields (e.g., keys, protocols, username) for any existing secret inside `secrets.json`, then run:

```shell
docker compose up -d --force-recreate <service_name>
```

### Deleting a secret

Delete its entry from `secrets.json`, then run:

```shell
docker compose up -d --force-recreate <service_name>
```

### Splunk HEC token secret

To keep the HEC token out of `.env` and out of `docker inspect` (so it is not visible in the container's environment), use a **Docker Compose secret**. The app supports the `SPLUNK_HEC_TOKEN_FILE` convention: when set, the token is read from that path instead of from the `SPLUNK_HEC_TOKEN` env var. Only the path is in the environment, not the token.

1. Create a file that contains only the token (e.g. `./secrets/splunk_hec_token`).

2. In `.env`, set the path to that file and leave `SPLUNK_HEC_TOKEN` unset or empty:
   ```
   SPLUNK_HEC_TOKEN_SECRET_FILE=./secrets/splunk_hec_token
   ```

3. Recreate the worker-sender service. The compose file mounts the secret at `/run/secrets/splunk_hec_token` and sets `SPLUNK_HEC_TOKEN_FILE` to that path. The app reads the token from the file; the token itself never appears in `docker inspect` or `docker compose config`.
///

## Migration steps (docker compose only)

Managing SNMPv3 secrets previously required updating docker compose files using the manage_secrets.py script.
From SC4SNMP 1.15.0, this process has been simplified and can manage all SNMPv3 secrets using a single secrets.json file.

#### 1. For setups not yet migrated to latest version
First, delete all existing secrets from docker-compose.yaml using manage_secrets.py with the following flags:

| Flag                | Description                                          |
|---------------------|------------------------------------------------------|
| `--secret_name`     | Secret name                                          |
| `--path_to_compose` | Absolute path to directory with docker compose files |
| `--delete`          | Set this flag to true to delete the secret           |

This will delete the secret with a given name from all docker compose files. If this secret hasn't been deleted from `.env`
file, it will be removed from there.

#### 2. For setups already migrated to latest version
Manually delete the secrets from the docker-compose.yaml file under the worker-poller and worker-trap services.
Remove the corresponding entries from the .env file.

After deleting the secrets, follow the above steps to configure secrets.
