#Deployment Configuration

`values.yaml` is the main point of SC4SNMP management. You can check all the default values of Helm dependencies using:

```
microk8s helm3 inspect values splunk-connect-for-snmp/splunk-connect-for-snmp > values.yaml
```

The whole file is divided into the following parts:

For configuring endpoint for sending SNMP data:

- `splunk` - in case you use Splunk Enterprise/Cloud
- `sim` - in case you use Splunk Observability Cloud. More details: [sim configuration](sim-configuration.md)

For polling purposes:

- `scheduler` - more details: [scheduler configuration](scheduler-configuration.md)
- `poller` - more details: [poller configuration](poller-configuration.md)

For traps receiving purposes:

- `traps` - more details: [trap configuration](trap-configuration.md)
   
Shared components:

- `worker` - more details: [worker configuration](worker-configuration.md)
- `mongodb` - more details: [mongo configuration](mongo-configuration.md)
- `redis` - more details: [redis configuration](redis-configuration.md)

### Shared values
All the components have the `resources` field for adjusting memory resources:
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
