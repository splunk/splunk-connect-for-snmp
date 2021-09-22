# SPLUNK for Kubernetes installation

Below steps are sufficient for SCK installation for SC4SNMP project. In case you want to investigate more, all information about Splunk Connect for Kubernetes are available [here](https://github.com/splunk/splunk-connect-for-kubernetes).

## Instalation steps
### Add SCK repository to HELM
```
microk8s helm3 repo add splunk https://splunk.github.io/splunk-connect-for-kubernetes
```
### Create values file
In order to connect to SPLUNK instance, there's a need to create `values.yaml` file of this following structure filling variables marked with "###" (description below).
```yaml
#global settings
global:
  logLevel: info 
  splunk:
    hec:
      protocol: https
      insecureSSL: "true"
      host: ###SPLUNK_HOST###
      token: ###SPLUNK_TOKEN###
      port: ###SPLUNK_PORT###
  kubernetes:
    clusterName: ###CLUSTER_NAME###

#local config for logging chart
splunk-kubernetes-logging:
  # Enable chart
  enabled: true
  # Determine logging level per chart
  logLevel: info
  containers:
    logFormatType: cri
    logFormat: "%Y-%m-%dT%H:%M:%S.%N%:z"
  # Filter on Namespace to reduce log noise from all namespaces
  fluentd: 
    path: "/var/log/containers/*_sc4snmp_*.log,/var/log/containers/*_sck_*.log" 
  kubernetes:
    securityContext: true
  # Set journald path. Update to reflect MicroK8s systemd services. See MicroK8s Docs. 
  journalLogPath: /var/log/journal
  # Review flush intervals for Splunk Cloud vs Self-Managed back off timers
  buffer:
    "@type": memory
    total_limit_size: 600m
    chunk_limit_size: 10m
    chunk_limit_records: 100000
    flush_interval: 5s
    flush_thread_count: 1
    overflow_action: block
    retry_max_times: 10
    retry_type: periodic
  k8sMetadata:
  # Pod labels to collect
    podLabels:
      - app
      - k8s-app
      - release
      - environment
      - tier
  # In case snmp prefix is useful or if you want to remove "kube"
  sourcetypePrefix: "kube"
  splunk:
    hec:
      indexName: em_logs
  logs:
    sck:
      from:
        pod: sck-splunk-kubernetes-
        container: splunk-fluentd-k8s-
      multiline:
        firstline: /^\d{4}-\d{2}-\d{2}\s\d{2}\:\d{2}\:\d{2}\s\+\d{4}\s\[\w+\]\:/
        separator: "\n"
        flushInterval: 5
    
#local config for objects chart
splunk-kubernetes-objects:
  # enable or diable objects
  enabled: false
  rbac:
    create: true
  serviceAccount:
    create: true
    name: splunk-kubernetes-objects
  kubernetes:
    insecureSSL: true
  objects:
    core:
      v1:
        - name: pods
        - name: namespaces
        - name: component_statuses
        - name: nodes
        - name: services
        - name: events
          mode: watch
  splunk:
    hec:
      indexName: em_meta

#local config for metrics chart
splunk-kubernetes-metrics:
  # enable or disbale metrics
  enabled: false
  metricsInterval: 60s
  kubernetes:
    kubeletPort: 10255
    kubeletPortAggregator: 10250
    useRestClientSSL: false
    insecureSSL: true
  rbac:
    create: true
  serviceAccount:
    create: true
    name: splunk-kubernetes-metrics
  splunk:
    hec:
      indexName: em_metrics
  customFilters:
    node:
      tag: "kube.node.**"
      type: record_modifier
      body: |-
        <record>
          entity_type k8s_node
        </record>
    pod:
      tag: "kube.pod.**"
      type: record_modifier
      body: |-
        <record>
          entity_type k8s_pod

```
### Values description

Values required to be filled:

| Placeholder   | Description  | Example  | 
|---|---|---|
| ###SPLUNK_HOST###  | host address of splunk instance   | "i-08c221389a3b9899a.ec2.splunkit.io"  |
| ###SPLUNK_PORT###  | port number of splunk instance   | "8088"  |
| ###SPLUNK_TOKEN### | Splunk HTTP Event Collector token  | "450a69af-16a9-4f87-9628-c26f04ad3785"  |
| ###CLUSTER_NAME### | name of the cluster | "foo" |


In case you want to change index names (note that in this case you need to keep consistent names in Splunk instance and SC4SNMP values file), you can override this variables:

| Index type | variable | description | default value |
| --- | --- | --- | --- |
| Logs index | splunk-kubernetes-logging: splunk: hec: indexName: | name of the logs index | "em_index" |
| Meta index | splunk-kubernetes-objects: splunk: hec: indexName: | name of the meta index | "em_meta" |
| Metrics index |  splunk-kubernetes-metrics: splunk: hec: indexName: | name of the metrics index | "em_metrics" |

Other variables possible to override in case you need it:

| variable | description | default |
| --- | --- | --- |
| global: splunk: hec: protocol | port of splunk instance | "8088" |
| global: splunk: hec: protocol insecure_ssl| is insecure ssl allowed | "true" |

### Install SCK with HELM
```yaml
microk8s helm3 install sck-for-snmp -f sck_values.yaml splunk/splunk-connect-for-kubernetes
```

From now on you after every update of `values.yaml` you can use this command to propagate it:
``` bash
microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/snmp-installer --namespace=sc4snmp --create-namespace
```
