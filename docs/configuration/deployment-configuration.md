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

### Update Inventory and Profile
Inventory and profiles in `valuses.yaml` is quite expensive from Splunk Connect for SNMP perspective. 
It required several checks before applying changes. SC4SNMP was designed to prevent changes in inventory and profiles 
task more often than every 5 min. 
 
When changing inventory or profile need to be apply in `valuses.yaml` following steps need to be done:

1. Apply changes in `values.yaml` 
2. Check is inventory pod is still running by execute command 
   ```shell script
   microk8s kubectl -n sc4snmp get pods |grep inventory
   ```
   If command do not return any pods than follow next step in other case wait and execute command again till moment 
   when inventory job finish. 
3. Run upgrade command describe in [Installation Guide](../gettingstarted/sc4snmp-installation/#install-sc4snmp) 