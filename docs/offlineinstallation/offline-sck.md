# Splunk OpenTelemetry Collector for Kubernetes offline installation

## Local machine with internet access

To install Splunk OpenTelemetry Collector offline first one must download packed chart `splunk-otel-collector-<tag>.tgz` and the otel image `otel_image.tar`
from github release where `<tag>` is the current OpenTelemetry release tag. Both packages must be later moved to the installation server.

## Installation on the server
 
Otel image has to be imported to the `microk8s` registry with:

```bash
microk8s ctr image import otel_image.tar 
```

Imported package must be unpacked with the following command :

```bash
tar -xvf splunk-otel-collector-<tag>.tgz --exclude='._*'
```

In order to run Splunk OpenTelemetry Collector on your environment, replace `<>` variables according to the description presented below
```bash
microk8s helm3 install sck \
  --set="clusterName=<cluster_name>" \
  --set="splunkPlatform.endpoint=<splunk_endpoint>" \
  --set="splunkPlatform.insecureSkipVerify=<insecure_skip_verify>" \
  --set="splunkPlatform.token=<splunk_token>" \
  --set="logsEngine=otel" \
  --set="splunkPlatform.metricsEnabled=true" \
  --set="splunkPlatform.metricsIndex=em_metrics" \
  --set="splunkPlatform.index=em_logs" \
  splunk-otel-collector
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
microk8s helm3 install sck \
  --set="clusterName=my-cluster" \
  --set="splunkPlatform.endpoint=https://endpoint.example.com/services/collector" \
  --set="splunkPlatform.insecureSkipVerify=false" \
  --set="splunkPlatform.token=4d22911c-18d9-4706-ae7b-dd1b976ca6f7" \
  --set="splunkPlatform.metricsEnabled=true" \
  --set="splunkPlatform.metricsIndex=em_metrics" \
  --set="splunkPlatform.index=em_logs" \
  splunk-otel-collector
```

## Install Splunk OpenTelemetry Collector with HELM for Splunk Observability for Kubernetes

To run Splunk OpenTelemetry Collector on your environment, replace `<>` variables according to the description presented below

```bash
microk8s helm3 install sck
--set="clusterName=<cluster_name>"
--set="splunkObservability.realm=<realm>"
--set="splunkObservability.accessToken=<token>"
--set="splunkObservability.ingestUrl=<ingest_url>"
--set="splunkObservability.apiUrl=<api_url>"
--set="splunkObservability.metricsEnabled=true"
--set="splunkObservability.tracesEnabled=false"
--set="splunkObservability.logsEnabled=false"
splunk-otel-collector
```

### Variables description


| Placeholder   | Description  | Example  | 
|---|---|---|
| cluster_name  | name of the cluster | my_cluster |
| realm | Realm obtained from the Splunk Observability Cloud environment  | us0  |
| token | Token obtained from the Splunk Observability Cloud environment  | BCwaJ_Ands4Xh7Nrg |
| ingest_url | Ingest URL from the Splunk Observability Cloud environment | https://ingest..signalfx.com |
| api_url | API URL from the Splunk Observability Cloud environment  | https://api..signalfx.com |

An example of filled up command is:
```bash
microk8s helm3 install sck 
--set="clusterName=my_cluster"
--set="splunkObservability.realm=us0"
--set="splunkObservability.accessToken=BCwaJ_Ands4Xh7Nrg"
--set="splunkObservability.ingestUrl=https://ingest..signalfx.com"
--set="splunkObservability.apiUrl=https://api..signalfx.com"
--set="splunkObservability.metricsEnabled=true"
--set="splunkObservability.tracesEnabled=false"
--set="splunkObservability.logsEnabled=false"
splunk-otel-collector
```