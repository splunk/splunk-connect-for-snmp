#Deployment Configuration

`values.yaml` is the main point of SC4SNMP management. The most important variables are already there from the very beginning 
after executing:
```
microk8s helm3 inspect values splunk-connect-for-snmp/splunk-connect-for-snmp > values.yaml
```

The whole file is divided into the following components:

1. scheduler - more detail [scheduler configuration](scheduler-configuration.md)
2. worker - more detail [worker configuration](worker-configuration.md)
3. poller - more detail [poller configuration](poller-configuration.md)
3. sim - more detail [sim configuration](sim-configuration.md)
4. traps - more detail [trap configuration](trap-configuration.md)
5. mongodb - more detail [mongo configuration](mongo-configuration.md)
6. redis - more detail [redis configuration](redis-configuration.md)

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
Inventory and profiles in `values.yaml` is quite expensive from the Splunk Connect for SNMP perspective. 
It requires several checks before applying changes. SC4SNMP was designed to prevent changes in inventory and profiles 
task more often than every 5 min. 
 
When changing inventory or profile needs to be applied in `values.yaml` following steps need to be done:

1. Edit `values.yaml` 
2. Check is inventory pod is still running by an execute command
   
```shell
microk8s kubectl -n sc4snmp get pods | grep inventory
```
   
If the command does not return any pods, follow the next step. In another case, wait and execute the command again until the moment 
when inventory job finishes. 

If you really need to apply changes immediately, you can get around the limitation by deleting inventory job, with:

```shell
microk8s kubectl delete job/snmp-splunk-connect-for-snmp-inventory -n sc4snmp
```

After running this command, you can proceed with upgrading without a need to wait.
   
3. Run upgrade command described in [Installation Guide](../../gettingstarted/sc4snmp-installation#install-sc4snmp) 

NOTE: If you decide to change frequency of the profile without changing inventory data, the change will be reflected after 
next walk process for the host. Walk happens every `walk_interval` or on any change in inventory.