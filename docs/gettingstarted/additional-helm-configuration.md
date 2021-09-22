## Additional HELM configuration

`values.yaml` are the main point of SC4SNMP management. The most important variables are already there from the very beginning 
after executing:
```
microk8s helm3 inspect values splunk-connect-for-snmp/snmp-installer > values.yaml
```
The whole file is divided on following components:

1. scheduler
2. splunk
3. mib
4. mongodb
5. rabbitmq

### Shared values
All of the components have `resources` field for memory resources adjusting:
```yaml
  resources:
    limits:
      cpu: 1000m
      memory: 2Gi
    requests:
      cpu: 1000m
      memory: 2Gi
```
More informations about `resources` concept in [kuberentes documentation](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/).

Scheduler, MIB and Worker contain `logLevel` variable that indicates the level of logging for the pod.

### Scheduler values
| variable | description | example
| --- | --- | --- |
| index | indexes names, should be the same as the ones given in SCK configuration | event: em_logs / metrics: em_metrics / meta: em_meta |
| inventory | inventory.csv content, described in sc4snmp-configuration | 10.0.101.22,2c,public,basev1,300 |
| config | content of config.yaml | |

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

### RabbitMQ values
Values described here: https://github.com/bitnami/charts/tree/master/bitnami/rabbitmq in Parameters section.

### MongoDB values
Values described here: https://github.com/bitnami/charts/tree/master/bitnami/mongodb in Parameters section.