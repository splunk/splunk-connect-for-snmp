# Splunk Connect for Kubernetes installation

The below steps are sufficient for a SCK installation for the SC4SNMP project with Splunk Enterprise/Enterprise Cloud. 
To learn more about SCK [visit](https://github.com/signalfx/splunk-otel-collector-chart/blob/main/helm-charts/splunk-otel-collector/values.yaml).
Including configuration with Splunk Observability Cloud.

## Instalation steps
### Add SCK repository to HELM

```bash
microk8s helm3 repo add splunk-otel-collector-chart https://signalfx.github.io/splunk-otel-collector-chart
```
### Install SCK with HELM

In order to run SCK on your environment, replace `<>` variables according to the description presented below
```bash
microk8s helm3 upgrade --install sck \
  --set="clusterName=<cluster_name>" \
  --set="splunkPlatform.endpoint=<splunk_endpoint>" \
  --set="splunkPlatform.insecureSkipVerify=<insecure_skip_verify>" \
  --set="splunkPlatform.token=<splunk_token>" \
  --set="splunkPlatform.metricsEnabled=true" \
  --set="splunkPlatform.metricsIndex=em_metrics" \
  --set="splunkPlatform.index=em_logs" \
  splunk-otel-collector-chart/splunk-otel-collector
```

### Variables description


| Placeholder   | Description  | Example  | 
|---|---|---|
| splunk_endpoint  | host address of splunk instance   | https://endpoint.example.com:8088/services/collector  |
| insecure_skip_verify  | is insecure ssl allowed | false |
| splunk_token | Splunk HTTP Event Collector token  | 450a69af-16a9-4f87-9628-c26f04ad3785  |
| cluster_name | name of the cluster | my-cluster |

An example of filled up command is:
```bash
microk8s helm3 upgrade --install sck \
  --set="clusterName=my-cluster" \
  --set="splunkPlatform.endpoint=https://endpoint.example.com/services/collector" \
  --set="splunkPlatform.insecureSkipVerify=false" \
  --set="splunkPlatform.token=4d22911c-18d9-4706-ae7b-dd1b976ca6f7" \
  --set="splunkPlatform.metricsEnabled=true" \
  --set="splunkPlatform.metricsIndex=em_metrics" \
  --set="splunkPlatform.index=em_logs" \
  splunk-otel-collector-chart/splunk-otel-collector
```