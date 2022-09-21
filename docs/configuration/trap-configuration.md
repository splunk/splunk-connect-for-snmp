#Trap Configuration
A trap service is a simple server that can handle SNMP traps sent by SNMP devices like routers or switches.   

### Trap configuration file

Trap configuration is kept in `values.yaml` file in section traps.
`values.yaml` is being used during the installation process for configuring Kubernetes values.

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
`communities` define a version of SNMP protocol and SNMP community string which should be used. 
`communities` key is split by protocol version, supported values are `1` and `2c`. Under `version` section, SNMP community string can be defined. 

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
`usernameSecrets` key in the `traps` section define SNMPv3 secrets for trap messages sent by SNMP device. `usernameSecrets` define which secrets 
in "Secret" objects in k8s should be used, as a value it needs to put the name of "Secret" objects. 
More information on how to define the "Secret" object for SNMPv3 can be found in [SNMPv3 Configuration](snmpv3-configuration.md)

Example:
```yaml
traps:
    usernameSecrets:
      - sc4snmp-homesecure-sha-aes
      - sc4snmp-homesecure-sha-des
```   

### Define security engines ID for SNMPv3

SNMPv3 TRAPs mandate you configuring SNMP Engine ID of the TRAP sending application to USM users table of TRAP receiving 
application for each USM user. It is usually unique per the device, and SC4SNMP as a trap receiver has to be aware of 
which security engine ids to accept. Define all of them under `traps.securityEngineId` in `values.yaml`.

By default, it is set to one-element list: `[80003a8c04]`. 

Example:
```yaml
traps:
    securityEngineId: 
      - "80003a8c04"
```

Security engine id is a substitute of `-e` variable in `snmptrap`.
An example of SNMPv3 trap is:

```yaml
snmptrap -v3 -e 80003a8c04 -l authPriv -u snmp-poller -a SHA -A PASSWORD1 -x AES -X PASSWORD1 10.202.13.233 '' 1.3.6.1.2.1.2.2.1.1.1
```

### Define load balancer IP

`loadBalancerIP` is the IP address in the metallb pool. 
Example:

```yaml
traps:
  loadBalancerIP: 10.202.4.202
```

### Define number of traps server replica
`replicaCount` Defines the number of replicas for trap container should be 2x number of nodes. The default value is `2`. 
Example:
```yaml
traps:
  #For production deployments the value should be at least 2x the number of nodes
  # Minimum 2 for a single node
  # Minimum 6 for multi-node HA
  replicaCount: 2
```

### Define log level
Log level for trap can be set by changing the value for key `logLevel`. Allowed values are: `DEBUG`, `INFO`, `WARNING`, `ERROR`. 
The default value is `WARNING`

### Define annotations
In case you need to append some annotations to trap service, you can do it by setting `traps.service.annotations`, for ex.:

```yaml
traps:
  service:
    annotations:
      annotation_key: annotation_value
```