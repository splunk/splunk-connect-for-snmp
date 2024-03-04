# Trap Configuration

A trap service is a simple server that can handle SNMP traps sent by SNMP devices, such as routers or switches.   

### Trap configuration file

The trap configuration is kept in the `values.yaml` file in section traps.
`values.yaml` is used during the installation process for configuring Kubernetes values.

See the following trap example configuration:
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
`communities` defines a version of an SNMP protocol and an SNMP community string, which should be used. 
The `communities` key is split by protocol version, with `1` and `2c` as supported values. Under the `version` section, you can define the SNMP community string.

See the following example: 
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
The `usernameSecrets` key in the `traps` section defines the SNMPv3 secrets for the trap messages sent by the SNMP device. `usernameSecrets` defines which secrets 
in "Secret" objects in k8s should be used, as a value it needs the name of "Secret" objects. 
For more information on how to define the "Secret" object for SNMPv3, see [SNMPv3 Configuration](snmpv3-configuration.md).

See the following example:
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

By default, it is set to a one-element list: `[80003a8c04]`, for example: 

```yaml
traps:
    securityEngineId: 
      - "80003a8c04"
```

The security engine ID is a substitute of the `-e` variable in `snmptrap`.
The following is an example of an SNMPv3 trap:

```yaml
snmptrap -v3 -e 80003a8c04 -l authPriv -u snmp-poller -a SHA -A PASSWORD1 -x AES -X PASSWORD1 10.202.13.233 '' 1.3.6.1.2.1.2.2.1.1.1
```

### Define external gateway for traps

If you use SC4SNMP on a single machine, configure `loadBalancerIP`.
`loadBalancerIP` is the IP address in the metallb pool. 
See the following example:

```yaml
traps:
  loadBalancerIP: 10.202.4.202
```

If you want to use the SC4SNMP trap receiver in K8S cluster, configure `NodePort` instead. Use the following configuration:

```yaml
traps:
  service: 
    type: NodePort
    externalTrafficPolicy: Cluster
    nodePort: 30000
```

Using this method, the SNMP trap will always be forwarded to one of the trap receiver pods listening on port 30000 (like in the
example above, you can configure to any other port). So, it doesn't matter that IP address of which node you use. Adding
nodePort will make it end up in the correct place everytime. 

A good practice is to create an IP floating address/Anycast pointing to the healthy nodes, so the traffic is forwarded in case of the
failover. To do this, create an external LoadBalancer that balances the traffic between nodes.

### Define number of traps server replica
`replicaCount` defines that the number of replicas per trap container should be 2 times the number of nodes.
```yaml
traps:
  #For production deployments the value should be at least 2x the number of nodes
  # Minimum 2 for a single node
  # Minimum 6 for multi-node HA
  replicaCount: 2
```

### Define log level
The log level for trap can be set by changing the value for the `logLevel` key. The allowed values are`DEBUG`, `INFO`, `WARNING`, or `ERROR`. 
The default value is `WARNING`.

### Define annotations
In case you need to append some annotations to the `trap` service, you can do so by setting `traps.service.annotations`, for example:

```yaml
traps:
  service:
    annotations:
      annotation_key: annotation_value
```

### Aggregate traps
In case you want to see traps events collected as one event inside Splunk, you can enable it by setting `traps.aggregateTrapsEvents`, for example:
```yaml
traps:
  aggregateTrapsEvents: "true"
```

### Updating trap configuration
If you need to update part of the traps configuration, you can do it by editing the `values.yaml` and then running the following command to restart the pod deployment:
```
microk8s kubectl rollout restart deployment snmp-splunk-connect-for-snmp-trap -n sc4snmp
```

NOTE: The name of the deployment can differ based on the helm installation name. This can be checked with the following command: 
```
microk8s kubectl get deployments -n sc4snmp
```
