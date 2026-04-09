# Identifying Traps issues

## Wrong IP or port
The first possible answer to why traps are not sent to Splunk is that SNMP agents send trap messages to the wrong IP
address or port.

/// tab | microk8s
To check what is the correct address of traps server, run the following command:

```
microk8s kubectl -n sc4snmp get services
```

This command should output similar data:
```
NAME                                TYPE           CLUSTER-IP       EXTERNAL-IP      PORT(S)         AGE
snmp-redis-master                 ClusterIP      None             <none>           6379/TCP        113s
snmp-mibserver                      ClusterIP      10.152.183.163   <none>           80/TCP          113s
snmp-mongodb                        ClusterIP      10.152.183.118   <none>           27017/TCP       113s
snmp-redis-master                   ClusterIP      10.152.183.61    <none>           6379/TCP        113s
snmp-mongodb-metrics                ClusterIP      10.152.183.50    <none>           9216/TCP        113s
snmp-splunk-connect-for-snmp-trap   LoadBalancer   10.152.183.190   114.241.233.134   162:32180/UDP   113s
```

Check the `EXTERNAL-IP` of `snmp-splunk-connect-for-snmp-trap` and the second port number for this service. In this case
the full `snmp-splunk-connect-for-snmp-trap` address will be `114.241.233.134:32180`.

In case agents send traps to the correct address, but there is still no data in the `netops` index, there might be some
issues with credentials. These errors can be seen in logs of the `snmp-splunk-connect-for-snmp-trap` pod.
///

/// tab | docker compose
The trap server listens on the host IP on the port defined by `TRAPS_PORT` in `.env`. Check the current value:

```
TRAPS_PORT=162
```

SNMP agents should send traps to the host machine's IP address on that port.

In case agents send traps to the correct address, but there is still no data in the `netops` index, there might be some
issues with credentials. These errors can be seen in logs of the `sc4snmp-traps` container.
///


## Unknown SNMP community name encountered
In case of using community string for authentication purposes, the following error should be expected if the arriving trap
has a community string not configured in SC4SNMP:
```
2024-02-06 15:42:14,885 ERROR Security Model failure for device ('18.226.181.199', 42514): Unknown SNMP community name encountered
```

If this error occurs, check if the appropriate community is defined. See the
following example of a `public` community configuration:

/// tab | microk8s
Check `traps.communities` in `values.yaml`:

```yaml
traps:
  communities:
    2c:
      - public
```
///

/// tab | docker compose
Check `communities` in `traps-config.yaml`:

```yaml
communities:
  2c:
    - public
```
///

## Unknown SNMP security name encountered

While sending SNMP v3 traps in case of wrong username or engine id configuration, the following error should be expected:
```
2024-02-06 15:42:14,091 ERROR Security Model failure for device ('18.226.181.199', 46066): Unknown SNMP security name encountered
```

If this error occurs, verify that the correct username has been created ([SNMPv3 configuration](../configuration/snmpv3.md)).
After creating the secret, add it to `usernameSecrets` and check that the correct SNMP engine id is configured. See the following example with configured secret and engine id:

/// tab | microk8s
```yaml
traps:
  usernameSecrets:
    - my-secret-name
  securityEngineId:
    - "090807060504030201"
```
///

/// tab | docker compose
In `traps-config.yaml`:

```yaml
usernameSecrets:
  - my-secret-name
```

In `.env`:

```
SNMP_V3_SECURITY_ENGINE_ID=090807060504030201
```
///

## Authenticator mismatched

While sending SNMP v3 traps in case of wrong authentication protocol or password configuration, the following error should be expected:
```
2024-02-06 15:42:14,642 ERROR Security Model failure for device ('18.226.181.199', 54806): Authenticator mismatched
```
If this error occurs, verify that the correct authentication protocol and password has been created ([SNMPv3 configuration](../configuration/snmpv3.md)).
After creating the secret, add it to `usernameSecrets`. See the following example with configured secret:

/// tab | microk8s
```yaml
traps:
  usernameSecrets:
    - my-secret-name
```
///

/// tab | docker compose
In `traps-config.yaml`:

```yaml
usernameSecrets:
  - my-secret-name
```
///

## Ciphering services not available or ciphertext is broken
While sending SNMP v3 traps in case of wrong privacy protocol or password configuration, the following error should be expected:
```
2024-02-06 15:42:14,780 ERROR Security Model failure for device ('18.226.181.199', 48249): Ciphering services not available or ciphertext is broken
```
If this error occurs, verify that the correct privacy protocol and password has been created ([SNMPv3 configuration](../configuration/snmpv3.md)).
After creating the secret, add it to `usernameSecrets`. See the following example with configured secret:

/// tab | microk8s
```yaml
traps:
  usernameSecrets:
    - my-secret-name
```
///

/// tab | docker compose
In `traps-config.yaml`:

```yaml
usernameSecrets:
  - my-secret-name
```
///