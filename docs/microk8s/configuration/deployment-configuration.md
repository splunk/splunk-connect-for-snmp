#Deployment Configuration

The `values.yaml` is the main point of SC4SNMP management. You can check all the default values of Helm dependencies using the following command:

```
microk8s helm3 inspect values splunk-connect-for-snmp/splunk-connect-for-snmp > values.yaml
```

!!!info 
    If you intend to configure values.yaml, it is recommended to use the [basic template](https://github.com/splunk/splunk-connect-for-snmp/blob/main/examples/basic_template.yaml) as the foundation for your configuration.

The whole file is divided into the following parts:

To configure the endpoint for sending SNMP data:

- `splunk` - in case you use Splunk Enterprise/Cloud.
- `sim` - in case you use Splunk Observability Cloud. For more details see [sim configuration](sim-configuration.md).

For polling purposes:

- `scheduler` - For more details see [scheduler configuration](scheduler-configuration.md).
- `poller` - For more details see [poller configuration](poller-configuration.md).

For traps receiving purposes:

- `traps` - For more details see [trap configuration](trap-configuration.md).
   
Shared components:

- `inventory` - For more details see [inventory configuration](../poller-configuration#configure-inventory).
- `mibserver` - For more details see [mibserver configuration](../../mib-request.md).
- `mongodb` - For more details see [mongo configuration](mongo-configuration.md).
- `redis` - For more details see [redis configuration](redis-configuration.md).
- `ui` - For more details see [ui configuration](../gui/enable-gui.md).
- `worker` - For more details see [worker configuration](worker-configuration.md).

### Shared values
All the components have the following `resources` field for adjusting memory resources:

```yaml
  resources:
    limits:
      cpu: 1000m
      memory: 2Gi
    requests:
      cpu: 1000m
      memory: 2Gi
```
For more information about the concept of `resources`, see the [kuberentes documentation](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/).
For more information about scaling resources see the [scaling with microk8s](../../mk8s/k8s-microk8s-scaling).

There is an option to create common annotations across all services. It can be set by:

```yaml
commonAnnotations:
  annotation_key: annotation_value
```
