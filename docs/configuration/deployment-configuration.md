#Deployment Configuration

`values.yaml` are the main point of SC4SNMP management. The most important variables are already there from the very beginning 
after executing:
```
microk8s helm3 inspect values splunk-connect-for-snmp/splunk-connect-for-snmp > values.yaml
```

The whole file is divided into the following components:

1. scheduler - more detail [scheduler configuration](scheduler-configuration.md)
2. worker - more detail [worker configuration](worker-configuration.md)
3. poller - more detail [poller configuration](poller-configuration.md)
3. otel - more detail [otel configuration](otel-configuration.md)
4. traps - more detail [trap configuration](trap-configuration.md)
5. mongodb - more detail [mongo configuration](mongo-configuration.md)
6. rabbitmq - more detail [rabbitmq configuration](rabbitmq-configuration.md)

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