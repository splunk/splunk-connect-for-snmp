# Traps configuration

A trap service is a simple server that can handle SNMP traps sent by SNMP devices, such as routers or switches.

## Configuration fields

- `communities`: communities used for version `1` and `2c` of the SNMP. The default one is `public`.
- `usernameSecrets`: names of the SNMPv3 secrets to use for authenticating incoming traps. See [SNMPv3 configuration](snmpv3.md) for details.

## Configuration

/// tab | microk8s
Traps configuration is kept in the `traps` section of `values.yaml`:

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
  logLevel: "WARN"
  loadBalancerIP: 10.202.4.202
```

To apply changes, restart the trap deployment:

```shell
microk8s kubectl rollout restart deployment snmp-splunk-connect-for-snmp-trap -n sc4snmp
```

!!! info
    The name of the deployment can differ based on the helm installation name.
    This can be checked with the following command:
    ```
    microk8s kubectl get deployments -n sc4snmp
    ```
///

/// tab | docker compose
Traps configuration is stored in the `traps-config.yaml` file:

```yaml
communities:
  2c:
    - public
usernameSecrets: []
```

To apply changes, run the following command inside the `docker_compose` directory:

```shell
sudo docker compose up -d
```
///

## SNMPv3 security engine ID

In SNMPv3, every trap receiver must know the Security Engine ID of each sending device in advance. The receiver uses this ID together with the USM username, auth key, and priv key to authenticate incoming traps. Without the correct engine ID pre-registered, pysnmp rejects the trap before it even checks credentials.

/// tab | microk8s
Define all engine IDs under `traps.securityEngineId` in `values.yaml`:

```yaml
traps:
    securityEngineId:
      - "80003a8c04"
```

By default, it is set to a one-element list: `[80003a8c04]`.

The `securityEngineID` is a substitute of the `-e` variable in `snmptrap`.
The following is an example of an SNMPv3 trap:

```
snmptrap -v3 -e 80003a8c04 -l authPriv -u snmp-poller -a SHA -A PASSWORD1 -x AES -X PASSWORD1 10.202.13.233 '' 1.3.6.1.2.1.2.2.1.1.1
```
///

/// tab | docker compose
Set the engine IDs in `.env`:

```
SNMP_V3_SECURITY_ENGINE_ID=80003a8c04,aab123456
```
///

### Engine ID Discovery

If you are managing a large amount of traps agents it is possible to enable engine id discovery mode. The Engine ID Discovery feature automatically extracts the engine ID from each incoming SNMPv3 raw datagram and dynamically registers it with the SNMP engine, so the trap can be authenticated on the fly.
The engine ID is only registered if the username matches a known user and stored in database.

/// tab | microk8s
```yaml
traps:
  discoverEngineId: "true"
```
///

/// tab | docker compose
```
DISCOVER_ENGINE_ID=true
```
///

!!! info
    It is recommended to enable this feature only during the initial setup of the traps receiver. Once the engine IDs for all required devices in the network have been collected, disable the feature to prevent unwanted engine ID registration and to improve trap processing efficiency by eliminating the overhead of extracting the engine ID from every incoming message.

## Advanced configuration

### Aggregate traps

/// tab | microk8s
In case you want to see traps events collected as one event inside Splunk:

```yaml
traps:
  aggregateTrapsEvents: "true"
```
///

/// tab | docker compose
Set in `.env`:

```
SPLUNK_AGGREGATE_TRAPS_EVENTS=true
```
///

### Define external gateway for traps (microk8s only)

#### Using MetalLB LoadBalancer

If you use SC4SNMP on a multinode setup, configure `loadBalancerIP`.
`loadBalancerIP` should be an IP assigned from your MetalLB address pool in the same subnet as your cluster nodes can reach.

```yaml
traps:
  loadBalancerIP: 10.202.4.202
```

If you have enabled IPv6 dual-stack, provide both IPv4 and IPv6 addresses as a comma-separated list:

```yaml
traps:
  loadBalancerIP: 10.202.4.202,2001:0DB8:AC10:FE01:0000:0000:0000:0001
```

#### Using NodePort

For single-node clusters or simple setups without a load balancer:

```yaml
traps:
  service:
    type: NodePort
    externalTrafficPolicy: Cluster
    nodePort: 30000
```

#### Using Cloud Load Balancer

```yaml
traps:
  service:
    usemetallb: false
    annotations:
      service.beta.kubernetes.io/aws-load-balancer-type: external
      service.beta.kubernetes.io/aws-load-balancer-nlb-target-type: ip
      service.beta.kubernetes.io/aws-load-balancer-scheme: internal
```

### Traps port (docker compose only)

To change the external port exposed for the traps server, set in `.env`:

```
TRAPS_PORT=162
```
