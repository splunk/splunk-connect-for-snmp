# Mongo DB Configuration

Mongo DB is used as the database for keeping schedules.

### MongoDB configuration file

MongoDB configuration is kept in the `values.yaml` file in the `mongodb` section.
`values.yaml` is used during the installation process for configuring kubernetes values.

See the following example:
```yaml
mongodb:
  #Architecture, Architecture for Mongo deployments is immutable to move from standalone to replicaset will require a uninstall.
  # "replicaset" for HA or multi node deployments
  # "standalone" for single node non HA
  #architecture: "standalone"
  pdb:
    create: true
  #The following requests and limits are appropriate starting points
  #For productions deployments
  resources: 
    limits:
      cpu: 2
      memory: 2Gi
    requests:
      cpu: 750m
      memory: 512Mi    
  persistence:
    storageClass: "microk8s-hostpath"
  volumePermissions:
    enabled: true
```

It is recommended not to change this setting. If it is necessary to change it, see [MongoDB on Kubernetes](https://github.com/bitnami/charts/tree/master/bitnami/mongodb/). 
