#Trap Configuration
Trap service is a simple server which can handle SNMP traps sent by SNMP devices like rauter or switches.   

### Trap configuration file

Trap configuration is keep in `values.yaml` file in section traps.  To downland example file execute command:
```
curl -o ~/values.yaml https://raw.githubusercontent.com/splunk/splunk-connect-for-snmp/develop/values.yaml
```
`values.yaml` is being used during the installation process for configuring kubernetes values.

Trap example configuration:
```yaml
traps:
  communities:
    1:
      - public 
    2c:
      - public
      - homelab
  usernameSecrets:
    - secretv3
    - sc4snmp-homesecure-sha-des

  # Overrides the image tag whose default is the chart appVersion.
  logLevel: "WARN"
  # replicas: Number of replicas for trap container should be 2x number of nodes
  replicas: 2
  #loadBalancerIP: The IP address in the metallb pool
  loadBalancerIP: 10.202.4.202
  resources: 
    limits:
      cpu: 500m
      memory: 512Mi
    requests:
      cpu: 200m
      memory: 256Mi  
```

### Define communities 
`communities` define version of SNMP protocol and SNMP community string which should be use. 
`communities` key is split by protocol version, supported values are `1` and `2c`. Under version SNMP community string can be defined. 

Example: 
```yaml
traps:
  communities:
    1:
      - public 
    2c:
      - public
      - homelab
```

### Configure user secrets for SNMPv3 
`usernameSecrets` key in traps enable configure SNMPv3 secrets for trap messages sent by SNMP device. `usernameSecrets` define which secrets 
in "Secret" objects in k8s should be use, as a value it need to put name of "Secret" objects. 
More information how to define "Secrets" object for SNMPv3 can be found in [SNMPv3 Configuration](snmpv3-configuration.md)

Example:
```yaml
traps:
    usernameSecrets:
      - sc4snmp-homesecure-sha-aes
      - sc4snmp-homesecure-sha-des
```   
### Define load balancer IP
`loadBalancerIP` is the IP address in the metallb pool. 
Example:
```yaml
traps:
  loadBalancerIP: 10.202.4.202
```

### Define number of traps server replica
`replicas` Defines number of replicas for trap container should be 2x number of nodes. Default value is `2`. 
Example:
```yaml
traps:
  #For production deployments the value should be 2x the number of nodes
  # Minimum 2 for single node
  # Minimum 6 for multi node HA
  replicaCount: 2
```

### Define log level
Log level for trap can be set by changing value for key `logLevel`. Allowed value are: `DEBUG`, `INFO`, `WARNING`, `ERROR`. 
Default value is `WARNING`

 