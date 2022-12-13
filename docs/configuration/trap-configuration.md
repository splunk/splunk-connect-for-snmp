#Trap Configuration
A trap service is a simple server that can handle SNMP traps sent by SNMP devices like routers or switches.   

### Trap configuration file

The trap configuration is kept in the `values.yaml` file in section traps.
`values.yaml` is used during the installation process for configuring Kubernetes values.

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
`communities` define a version of SNMP protocol and SNMP community string, which should be used. 
`communities` key is split by protocol version, supported values are `1` and `2c`. Under the `version` section, SNMP community string can be defined. 

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
The `usernameSecrets` key in the `traps` section define SNMPv3 secrets for trap messages sent by SNMP device. `usernameSecrets` define which secrets 
in "Secret" objects in k8s should be used, as a value it needs the name of "Secret" objects. 
More information on how to define the "Secret" object for SNMPv3 can be found in [SNMPv3 Configuration](snmpv3-configuration.md).

Example:
```yaml
traps:
    usernameSecrets:
      - sc4snmp-homesecure-sha-aes
      - sc4snmp-homesecure-sha-des
```   

### Define security engines ID for SNMPv3

SNMPv3 TRAPs require the configuration SNMP Engine ID of the TRAP sending application for the USM users table of the TRAP receiving 
application for each USM user. The SNMP Engine ID is usually unique for the device, and the SC4SNMP as a trap receiver has to be aware of 
which security engine IDs to accept. Define all of them under `traps.securityEngineId` in `values.yaml`.

By default, it is set to one-element list: `[80003a8c04]`. 

Example:
```yaml
traps:
    securityEngineId: 
      - "80003a8c04"
```

Security engine ID is a substitute of the `-e` variable in `snmptrap`.
An example of SNMPv3 trap is:

```yaml
snmptrap -v3 -e 80003a8c04 -l authPriv -u snmp-poller -a SHA -A PASSWORD1 -x AES -X PASSWORD1 10.202.13.233 '' 1.3.6.1.2.1.2.2.1.1.1
```

### Define external gateway for traps

If you use SC4SNMP standalone, configure `loadBalancerIP`.
`loadBalancerIP` is the IP address in the metallb pool. 
Example:

```yaml
traps:
  loadBalancerIP: 10.202.4.202
```

If you want to use SC4SNMP trap receiver in K8S cluster, configure `NodePort` instead. The snippet of config is:

```yaml
traps:
  service: 
    type: NodePort
    externalTrafficPolicy: Cluster
    nodePort: 30000
```

Using this method, SNMP trap will always be forwarded to one of the trap receiver pods listening on port 30000 (as in the
example above, remember - you can configure any other port). So doesn't matter IP address of which node you use, adding
nodePort will make it end up in a correct place everytime. 

Here, good practice is to create IP floating address/Anycast pointing to the healthy nodes, so the traffic is forwarded in case of the
failover. The best way is to create external LoadBalancer which balance the traffic between nodes.

### Define number of traps server replica
`replicaCount` defines that the number of replicas for trap container should be 2x number of nodes. The default value is `2`. 
Example:
```yaml
traps:
  #For production deployments the value should be at least 2x the number of nodes
  # Minimum 2 for a single node
  # Minimum 6 for multi-node HA
  replicaCount: 2
```

### Define log level
The log level for trap can be set by changing the value for the `logLevel` key. The allowed values are: `DEBUG`, `INFO`, `WARNING`, `ERROR`. 
The default value is `WARNING`.

### Define annotations
In case you need to append some annotations to the `trap` service, you can do so by setting `traps.service.annotations`, for ex.:

```yaml
traps:
  service:
    annotations:
      annotation_key: annotation_value
```
