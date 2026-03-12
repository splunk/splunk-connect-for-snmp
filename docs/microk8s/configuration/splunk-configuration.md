# Splunk configuration

Configure the Splunk (HEC) endpoint for sending SNMP data. You can provide the HEC token as plaintext, from a Kubernetes Secret, or from a file (e.g. Vault Agent Injector).

## Splunk section (values)

| Variable                   | Description                                                                 | Default                                |
|----------------------------|-----------------------------------------------------------------------------|----------------------------------------|
| `enabled`                  | Enables sending data to Splunk                                              | `true`                                 |
| `protocol`                 | The protocol of the HEC endpoint: `https` or `http`                         | `https`                                |
| `port`                     | The port of the HEC endpoint                                                | `8088`                                 |
| `host`                     | IP address or a domain name of a Splunk instance                            |                                        |
| `path`                     | URN to Splunk collector                                                     | `/services/collector`                  |
| `token`                    | Splunk HTTP Event Collector token (plaintext). Omit when using `tokenSecretRef` or `tokenFilePath`. | `00000000-0000-0000-0000-000000000000` |
| `tokenSecretRef`           | Reference to an existing Kubernetes Secret containing the HEC token. When set, the chart does not create a Secret from `token`. See [Using a Kubernetes secret for the HEC token](#using-a-kubernetes-secret-for-the-hec-token) below. | `name: ""`, `key: "hec_token"` |
| `tokenFilePath`            | Path to a file containing the HEC token (e.g. from Vault Agent Injector). When set, the chart sets `SPLUNK_HEC_TOKEN_FILE` and does not set `SPLUNK_HEC_TOKEN` from a Secret. See [Token from file (e.g. Vault injector)](#token-from-file-eg-vault-injector) below. | `""` |
| `insecureSSL`              | Skip certificate verification for the HEC endpoint when using HTTPS        | `false`                                |
| `sourcetypeTraps`          | Source type for trap events                                                 | `sc4snmp:traps`                        |
| `sourcetypePollingEvents`  | Source type for non-metric polling event                                    | `sc4snmp:event`                        |
| `sourcetypePollingMetrics` | Source type for metric polling event                                        | `sc4snmp:metric`                       |
| `eventIndex`               | Name of the event index                                                     | `netops`                               |
| `metricsIndex`             | Name of the metrics index                                                   | `netmetrics`                           |

## Using a Kubernetes secret for the HEC token

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

You can provide the HEC token via a **file** (e.g. injected by Vault Agent Injector or another provider). Set `splunk.tokenFilePath` to the path where the token file is mounted. The chart sets `SPLUNK_HEC_TOKEN_FILE` and does not set `SPLUNK_HEC_TOKEN` from a Secret. The application reads the token from that file.

Add injector annotations for your provider (Vault or other) via `worker.podAnnotations`.

**Important:** The file must contain only the token value (not JSON). Use an inject template so the mounted file has just the token.

**Example:**

```yaml
splunk:
  enabled: true
  host: "splunk.example.com"
  protocol: "https"
  port: "8088"
  tokenFilePath: /vault/secrets/splunk-hec-token

worker:
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
