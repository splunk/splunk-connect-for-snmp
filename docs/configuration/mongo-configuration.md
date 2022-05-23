#Mongo DB Configuration
Mongo DB is used as the database for keeping schedules.

### Mongo DB configuration file

Mongo DB configuration is kept in `values.yaml` file in section `mongodb`.
`values.yaml` is being used during the installation process for configuring kubernetes values.

Example:
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

The recommendation is to do not change this setting. In case of need to change it please follow documentation: [MongoDB on Kubernetes](https://github.com/bitnami/charts/tree/master/bitnami/mongodb/)  
