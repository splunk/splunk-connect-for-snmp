#RabbitMQ configuration
RabbitMQ is a service with is used as queue service for SC4SNMP. It is queuing tasks like SNMP Walk and GETs.  

### RabbitMQ configuration file

RabbitMQ configuration is keep in `values.yaml` file in section `rabbitmq`.  To downland example file execute command:
```
curl -o ~/values.yaml https://raw.githubusercontent.com/splunk/splunk-connect-for-snmp/develop/values.yaml
```
`values.yaml` is being used during the installation process for configuring kubernetes values.

Example:
```yaml
rabbitmq:
  pdb:
    create: true
  replicaCount: 1
  persistence:
    enabled: true
    storageClass: "microk8s-hostpath"
  volumePermissions:
    enabled: true
```

Recommendation is to do not change this setting. In case of need to change it please follow documentation: [RabbitMQ on Kubernetes](https://github.com/bitnami/charts/tree/master/bitnami/rabbitmq/) 