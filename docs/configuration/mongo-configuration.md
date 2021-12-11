#Mongo DB Configuration
Mongo DB is used as database for keeping schedules.

### Mongo DB configuration file

Mongo DB configuration is keep in `values.yaml` file in section `mongodb`.  To downland example file execute command:
```
curl -o ~/values.yaml https://raw.githubusercontent.com/splunk/splunk-connect-for-snmp/develop/values.yaml
```
`values.yaml` is being used during the installation process for configuring kubernetes values.

Example:
```yaml
mongodb:
  #Architecture
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

Recommendation is to do not change this setting. In case of need to change it please follow documentation: [MongoDB on Kubernetes](https://github.com/bitnami/charts/tree/master/bitnami/mongodb/)  
