## Basic SC4SNMP values.yaml template

Example 1: Traps and polling functionality enabled, sending data to Splunk:

```yaml
splunk:
  enabled: true
  protocol: https
  host: ###SPLUNK_HOST###
  token: ###SPLUNK_TOKEN###
  insecureSSL: "false"
  port: "###SPLUNK_PORT###"
traps:
  communities:
    2c:
      - public
  loadBalancerIP: ###TRAP_RECEIVER_IP###
scheduler:
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
  inventory: |
    address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
    ###POLLED_DEVICE_IP###,,2c,public,,,3000,generic_switch,,
```

Example 2: Polling functionality enabled, sending data to SIM:

```yaml
splunk:
  enabled: false
sim:
  enabled: true
  signalfxToken: ###SIGNALFX_TOKEN###
  signalfxRealm: ###SIGNALFX_REALM###
scheduler:
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
  inventory: |
    address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
    ###POLLED_DEVICE_IP###,,2c,public,,,3000,generic_switch,,
```

Splunk related placeholders to fill:

| Placeholder   | Description  | Example  | 
|---|---|---|
| ###SPLUNK_HOST###  | host address of splunk instance   | "i-08c221389a3b9899a.ec2.splunkit.io"  | 
| ###SPLUNK_PORT###  | port number of splunk instance   | "8088"  | 
| ###SPLUNK_TOKEN### | Splunk HTTP Event Collector token  | 450a69af-16a9-4f87-9628-c26f04ad3785  |

Splunk optional variables can be configured:

| variable | description | default |
| --- | --- | --- |
| splunk.protocol | port of splunk instance| https |
| splunk.insecure_ssl| is insecure ssl allowed | "true" |
| splunk.eventIndex | name of the events index | "netops" |
| splunk.metricsIndex | name of the metrics index | "netmetrics" |

Splunk Infrastructure Monitoring placeholders to fill:

| Placeholder   | Description  | Example | 
| --- | --- | -- |
| ###SIGNALFX_TOKEN### | SIM token which can be use for ingesting date vi API | nBCsdc_Ands4Xh7Nrg |
| ###SIGNALFX_REALM### | Real of SIM | us1 |

Shared placeholders to fill:

| Placeholder            | Description                           | Example       | 
|------------------------|---------------------------------------|---------------|
| ###TRAP_RECEIVER_IP### | SHARED IP address used for SNMP Traps | 10.202.18.166 |
| ###POLLED_DEVICE_IP### | IP address of the device to poll from | 56.22.180.166 |

Note: In case of standalone SC4SNMP installation, `###TRAP_RECEIVER_IP###` should be the IP address of the machine
where SC4SNMP is installed.