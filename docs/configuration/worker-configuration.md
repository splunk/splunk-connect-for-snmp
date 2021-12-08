# Worker Configuration
Worker is a service with is responsible for tasks execution like: SNMP Walk, GET or serve Trap messages.  

### Worker configuration file

Worker configuration is keep in `values.yaml` file in section `worker`.  To downland example file execute command:
```
curl -o ~/values.yaml https://raw.githubusercontent.com/splunk/splunk-connect-for-snmp/develop/values.yaml
```
`values.yaml` is being used during the installation process for configuring kubernetes values.

```yaml
worker:
  # replicas: Number of replicas for worker container should two or more
  replicas: 2
  logLevel: "WARN"
```

### Define number of worker server replica
`replicas` Defines number of replicas for worker container should be 2x number of nodes. Default value is `2`. 
Example:
```yaml
worker:
  replicas: 2
``` 

### Define log level
Log level for trap can be set by changing value for key `logLevel`. Allowed value are: `DEBUG`, `INFO`, `WARN`, `ERROR`. 
Default value is `WARN`