### Create SNMP v3 users

Configuration of SNMP v3, when supported by the monitored devices, is the most secure choice available
for authentication and data privacy. Each set of credentials will be stored as "Secret" objects in k8s
and will be referenced in the values.yaml. This allows the secret to being created once including automation
by third-party password managers then consumed without storing sensitive data in plain text.

```bash
# <secretname>=Arbitrary name of the secret often the same as the username or prefixed with "sc4snmp-"
# <namespace>=Namespace used to install sc4snmp
# <username>=the SNMPv3 Username
# <key>=key note must be at least 8 char long subject to target limitations
# <authProtocol>=One of SHA (SHA1) or MD5 
# <privProtocol>=One of AES or DES 
# Note MD5 and DES are considered insecure but must be supported for standards compliance
microk8s kubectl create -n <namespace> secret generic <secretname> \
  --from-literal=userName=<username> \
  --from-literal=authKey=<key> \
  --from-literal=privKey=<key> \
  --from-literal=authProtocol=<authProtocol> \
  --from-literal=privProtocol=<privProtocol> 
```

Configured credentials can be use in [poller](poller-configuration.md) and [trap](trap-configuration.md) services. 
In services configuration, `secretname` needs to be provided. 
