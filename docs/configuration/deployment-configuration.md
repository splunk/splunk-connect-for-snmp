#Deployment Configuration

`values.yaml` are the main point of SC4SNMP management. The most important variables are already there from the very beginning 
after executing:
```
microk8s helm3 inspect values splunk-connect-for-snmp/splunk-connect-for-snmp --version <VERSION_TAG> > values.yaml
```
| variable | description | default |
|---|---|---|
|VERSION_TAG| is a tag of build eg. 0.11.0-beta.22 | none|

The whole file is divided into the following components:

1. scheduler
2. worker
3. poller
4. traps
5. mongodb
6. rabbitmq

### Shared values
All of the components have the `resources` field for adjusting memory resources:
```yaml
  resources:
    limits:
      cpu: 1000m
      memory: 2Gi
    requests:
      cpu: 1000m
      memory: 2Gi
```
More information about the concept of `resources` can be found in the [kuberentes documentation](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/).

Scheduler, MIB and Worker contain a `logLevel` variable that indicates the level of logging for the pod.

### Traps values
| variable   | Description  | Example  | 
|---|---|---|
| loadBalancerIP | shared IP  | 10.0.101.22 |