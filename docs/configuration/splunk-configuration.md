# Splunk configuration

Configure the Splunk HTTP Event Collector (HEC) endpoint for sending SNMP data.

/// tab | microk8s

You can provide the HEC token as plaintext, from a Kubernetes Secret, or from a file (e.g. Vault Agent Injector).

## Configuration reference

| Variable                   | Description                                                                 | Default                                |
|----------------------------|-----------------------------------------------------------------------------|----------------------------------------|
| `enabled`                  | Enables sending data to Splunk                                              | `true`                                 |
| `protocol`                 | The protocol of the HEC endpoint: `https` or `http`                         | `https`                                |
| `port`                     | The port of the HEC endpoint                                                | `8088`                                 |
| `host`                     | IP address or a domain name of a Splunk instance                            |                                        |
| `path`                     | URN to Splunk collector                                                     | `/services/collector`                  |
| `token`                    | Splunk HTTP Event Collector token (plaintext). Omit when using `tokenSecretRef` or `tokenFilePath`. | `00000000-0000-0000-0000-000000000000` |
| `tokenSecretRef`           | Reference to an existing Kubernetes Secret containing the HEC token. When set, the chart does not create a Secret from `token`. See [Using a Kubernetes Secret for the HEC token](#using-a-kubernetes-secret-for-the-hec-token) below. | `name: ""`, `key: "hec_token"` |
| `tokenFilePath`            | Path to a file containing the HEC token (e.g. from Vault Agent Injector). When set, the chart sets `SPLUNK_HEC_TOKEN_FILE` and does not set `SPLUNK_HEC_TOKEN` from a Secret. See [Token from file (e.g. Vault injector)](#token-from-file-eg-vault-injector) below. | `""` |
| `insecureSSL`              | Skip certificate verification for the HEC endpoint when using HTTPS        | `false`                                |
| `sourcetypeTraps`          | Source type for trap events                                                 | `sc4snmp:traps`                        |
| `sourcetypePollingEvents`  | Source type for non-metric polling event                                    | `sc4snmp:event`                        |
| `sourcetypePollingMetrics` | Source type for metric polling event                                        | `sc4snmp:metric`                       |
| `eventIndex`               | Name of the event index                                                     | `netops`                               |
| `metricsIndex`             | Name of the metrics index                                                   | `netmetrics`                           |

## Using a Kubernetes Secret for the HEC token

Instead of putting the HEC token in plaintext in `splunk.token`, you can reference an existing Kubernetes Secret. This is recommended for production and when using a secrets manager.

**Behavior:** The chart provides the token to the application as the environment variable `SPLUNK_HEC_TOKEN` from a Secret via `secretKeyRef`. Any system that creates or syncs a normal Kubernetes Secret will work. The Secret must be in the **same namespace** as the release.

1. **Create the Secret** in the same namespace as the release, with the token under the key `hec_token` (or another key you specify):

```bash
kubectl create secret generic my-splunk-hec-secret \
  --from-literal=hec_token='YOUR_HEC_TOKEN' \
  -n sc4snmp
```

2. **Configure the chart** — leave `splunk.token` empty and set `splunk.tokenSecretRef`:

```yaml
splunk:
  enabled: true
  host: "splunk.example.com"
  protocol: "https"
  port: "8088"
  tokenSecretRef:
    name: my-splunk-hec-secret   # name of your Secret
    key: hec_token               # optional; default is hec_token
```

If both `token` and `tokenSecretRef.name` are set, `tokenSecretRef` takes precedence and the chart does not create a Secret from `token`.

**Startup:** Pods will stay in `CreateContainerConfigError` until the referenced Secret exists. With External Secrets or similar, ensure the Secret is synced before or with the Helm release.

**Rotation:** The token is read at pod start. After rotating the token in the vault and updating the Secret, restart the relevant deployments (e.g. worker, traps) to pick up the new value.

## Token from file (e.g. Vault injector)

You can provide the HEC token via a **file** (e.g. injected by Vault Agent Injector or another provider). Set `splunk.tokenFilePath` to the path where the token file is mounted. The chart sets `SPLUNK_HEC_TOKEN_FILE` only on the **sender** deployment (the only component that sends data to Splunk HEC). Add injector annotations only on the sender: `worker.sender.podAnnotations`. Do not use `worker.podAnnotations` for the token so other worker types and traps are not injected unnecessarily.

**Important:** The file must contain only the token value. Use an inject template so the mounted file has just the token.

**Example:**

```yaml
splunk:
  enabled: true
  host: "splunk.example.com"
  protocol: "https"
  port: "8088"
  tokenFilePath: /vault/secrets/splunk-hec-token

worker:
  sender:
    podAnnotations:
      vault.hashicorp.com/agent-inject: "true"
      vault.hashicorp.com/role: "sc4snmp"
      vault.hashicorp.com/agent-inject-secret-splunk-hec-token: "secret/data/splunk"
      vault.hashicorp.com/agent-inject-template-splunk-hec-token: |
        {{- with secret "secret/data/splunk" -}}
        {{ .Data.data.token }}
        {{- end }}
```

`tokenFilePath` must match where the injector writes the file: the annotation `agent-inject-secret-<name>` uses `<name>` as the filename under `/vault/secrets/`, so the path is `/vault/secrets/<name>` (e.g. `/vault/secrets/splunk-hec-token`). Adjust the template key (e.g. `{{ .Data.data.token }}`) if your Vault secret uses a different field name.

///

/// tab | docker compose

All Splunk connection settings are configured through environment variables in the `.env` file.

## Configuration reference

| Variable                                  | Description                                                                                                                           |
|-------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------|
| `SPLUNK_HEC_HOST`                         | IP address or a domain name of a Splunk instance to send data to                                                                      |
| `SPLUNK_HEC_PROTOCOL`                     | The protocol of the HEC endpoint: `https` or `http`                                                                                   |
| `SPLUNK_HEC_PORT`                         | The port of the HEC endpoint                                                                                                          |
| `SPLUNK_HEC_TOKEN`                        | Splunk HTTP Event Collector token (plaintext). Omit when using `SPLUNK_HEC_TOKEN_SECRET_FILE`.                                       |
| `SPLUNK_HEC_TOKEN_SECRET_FILE`            | Path on the host to a file containing the HEC token (worker-sender only). The app reads the token from the mounted file; only the path is in the container environment, not the token itself. See [HEC token as a Docker secret](#hec-token-as-a-docker-secret) below. |
| `SPLUNK_HEC_INSECURESSL`                  | Whether to skip checking the certificate of the HEC endpoint when sending data over HTTPS                                             |
| `SPLUNK_HEC_PATH`                         | Path for the HEC endpoint                                                                                                             |
| `SPLUNK_SOURCETYPE_TRAPS`                 | Splunk sourcetype for trap events                                                                                                     |
| `SPLUNK_SOURCETYPE_POLLING_EVENTS`        | Splunk sourcetype for non-metric polling events                                                                                       |
| `SPLUNK_SOURCETYPE_POLLING_METRICS`       | Splunk sourcetype for metric polling events                                                                                           |
| `SPLUNK_HEC_INDEX_EVENTS`                 | Name of the Splunk event index                                                                                                        |
| `SPLUNK_HEC_INDEX_METRICS`                | Name of the Splunk metrics index                                                                                                      |
| `SPLUNK_AGGREGATE_TRAPS_EVENTS`           | When set to `true`, collects trap events as a single event inside Splunk                                                              |
| `SPLUNK_METRIC_NAME_HYPHEN_TO_UNDERSCORE` | Replaces hyphens with underscores in generated metric names to ensure compatibility with Splunk's metric schema                       |
| `SPLUNK_LOG_INDEX`                        | Event index in Splunk where logs from Docker containers are sent. See [Sending logs to Splunk](../dockercompose/9-splunk-logging.md). |

## HEC token as a Docker secret

To keep the HEC token out of `.env` and out of `docker inspect` (so it is not visible in the container's environment), use a **Docker Compose secret**. When `SPLUNK_HEC_TOKEN_SECRET_FILE` is set, the app reads the token from that file path instead of from `SPLUNK_HEC_TOKEN`. Only the path is in the environment, not the token.

1. Create a file that contains only the token (e.g. `./secrets/splunk_hec_token`).

2. In `.env`, set the path to that file and leave `SPLUNK_HEC_TOKEN` unset or empty:

   ```
   SPLUNK_HEC_TOKEN_SECRET_FILE=./secrets/splunk_hec_token
   ```

3. Recreate the worker-sender service. The compose file mounts the secret at `/run/secrets/splunk_hec_token` and sets `SPLUNK_HEC_TOKEN_FILE` to that path. The app reads the token from the file; the token itself never appears in `docker inspect` or `docker compose config`.

///