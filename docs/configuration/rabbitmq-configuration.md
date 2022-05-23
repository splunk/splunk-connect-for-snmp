#RabbitMQ configuration
RabbitMQ is a service with is used as a queue service for SC4SNMP. It is queuing tasks like SNMP Walk and GETs.  

### RabbitMQ configuration file

RabbitMQ configuration is keep in `values.yaml` file in section `rabbitmq`.
`values.yaml` is being used during the installation process for configuring Kubernetes values.

Example:
```yaml
rabbitmq:
  pdb:
    create: true
  #For HA configuration at least three replicas should be used
  replicaCount: 1
  persistence:
    enabled: true
    storageClass: "microk8s-hostpath"
  volumePermissions:
    enabled: true
  #The following requests and limits are appropriate starting points
  #For productions deployments
  resources: 
    limits:
      cpu: 2
      memory: 2Gi
    requests:
      cpu: 750m
      memory: 512Mi    
```

The recommendation is to do not to change this setting. In case of need to change it please follow documentation: [RabbitMQ on Kubernetes](https://github.com/bitnami/charts/tree/master/bitnami/rabbitmq/) 
