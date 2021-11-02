## Additional HELM configuration

`deployment_values.yaml` are the main point of SC4SNMP management. The most important variables are already there from the very beginning 
after executing:
```
microk8s helm3 inspect values splunk-connect-for-snmp/splunk-connect-for-snmp > values.yaml
```
The whole file is divided into the following components:

1. scheduler
2. splunk
3. mib
4. mongodb
5. rabbitmq

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
Note, that when your environment contains big amount of memory and CPU you should increase limits for all of the pods (mib, scheduler, worker, traps), as long until it works stably.
More information about the concept of `resources` can be found in the [kuberentes documentation](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/).

Scheduler, MIB and Worker contain a `logLevel` variable that indicates the level of logging for the pod.

### Scheduler values
| variable | description | example
| --- | --- | --- |
| index | indexes names, should be the same as the ones given in SCK configuration | event: em_logs / metrics: em_metrics / meta: em_meta |

### Splunk values
| variable   | Description  | Example  | 
|---|---|---|
| host | host address of splunk instance   | i-08c221389a3b9899a.ec2.splunkit.io  | 
| token | Splunk HTTP Event Collector token  | 450a69af-16a9-4f87-9628-c26f04ad3785  |
| port | port of splunk instance    | "8088"  |
| insecureSSL | is insecure ssl allowed | "true" |
| clusterName | name of the cluster | "foo" |

### Traps values
| variable   | Description  | Example  | 
|---|---|---|
| loadBalancerIP | shared IP  | 10.0.101.22 |
