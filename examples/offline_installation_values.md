## Offline SC4SNMP values.yaml template

```yaml
splunk:
  enabled: true
  protocol: https
  host: ###SPLUNK_HOST###
  token: ###SPLUNK_TOKEN###
  insecureSSL: "false"
  port: "###SPLUNK_PORT###"
image:
  #Fill ###TAG## with the SC4SNMP version downloaded before with docker pull command
  # according to the documentation: https://splunk.github.io/splunk-connect-for-snmp/main/offlineinstallation/offline-sc4snmp/
  tag: ###TAG###
  pullPolicy: Never
traps:
  communities:
    2c:
      - public
      - homelab
  replicaCount: 1
  loadBalancerIP: ###TRAP_RECEIVER_IP###
worker:
  trap:
    replicaCount: 1
  poller:
    replicaCount: 2
  sender:
    replicaCount: 1
  logLevel: "INFO"
scheduler:
  logLevel: "INFO"
  profiles: |
    generic_switch:
      frequency: 300
        varBinds:
          - ['SNMPv2-MIB', 'sysDescr']
          - ['SNMPv2-MIB', 'sysName', 0]
          - ['TCP-MIB', 'tcpActiveOpens']
          - ['TCP-MIB', 'tcpAttemptFails']
          - ['IF-MIB']
poller:
  usernameSecrets:
    - sc4snmp-hlab-sha-aes
    - sc4snmp-hlab-sha-des
  inventory: |
    address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
    10.0.0.1,,3,,sc4snmp-hlab-sha-aes,,1800,generic_switch,,
    10.0.0.199,,2c,public,,,3000,,,True
    10.0.0.100,,3,,sc4snmp-hlab-sha-des,,1800,generic_switch,,
mongodb:
  image:
    pullPolicy: Never
redis:
  image:
    pullPolicy: Never
mibserver:
  image:
    pullPolicy: Never
```
    
Fill `###` variables according to the description from [online installation](https://splunk.github.io/splunk-connect-for-snmp/main/gettingstarted/sc4snmp-installation/#configure-splunk-enterprise-or-splunk-cloud-connection).

Additionally, fill `###TAG###` ith the same tag used before to `docker pull` an SC4SNMP image.