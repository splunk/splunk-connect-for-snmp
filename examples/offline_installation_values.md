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