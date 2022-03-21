# Worker Configuration
The worker is a service with is responsible for tasks execution like SNMP Walk, GET, or processing trap messages.  

### Worker configuration file

Worker configuration is kept in `values.yaml` file in section `worker`.  To downland example file execute the command:
```
curl -o ~/values.yaml https://raw.githubusercontent.com/splunk/splunk-connect-for-snmp/develop/values.yaml
```
`values.yaml` is being used during the installation process for configuring Kubernetes values.

```yaml
worker:
  # replicas: The number of replicas for worker containers should be two or more
  replicaCount: 2
  #Log level one of INFO, WARNING, CRITICAL, DEBUG, ERROR
  logLevel: "WARNING"
  #The following resource specification is appropriate for most deployments to scale the
  #Environment increase the number of workers rather than the resources per container
  resources:
    limits:
        cpu: 2        
        memory: 512Mi
    requests:
      cpu: 500m
      memory: 128Mi
```
