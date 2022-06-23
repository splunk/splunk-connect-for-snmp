# SC4SNMP Helm installation

The basic installation process and configuration used in this section are typical 
for single node non HA deployments and do not have resource requests and limits.
See the configuration sections for mongo, redis, scheduler, worker, and traps for guidance
on production configuration.

### Add SC4SNMP repository
```
microk8s helm3 repo add splunk-connect-for-snmp https://splunk.github.io/splunk-connect-for-snmp
microk8s helm3 repo update
```
Now the package should be visible in `helm3` search command result:
``` bash
microk8s helm3 search repo snmp
```
Example output:
``` 
NAME                                               CHART VERSION  APP VERSION    DESCRIPTION                           
splunk-connect-for-snmp/splunk-connect-for-snmp        1.0.0        1.0.0       A Helm chart for SNMP Connect for SNMP
```

### Download and modify values.yaml
```yaml
splunk:
  enabled: true
  protocol: https
  host: ###SPLUNK_HOST###
  token: ###SPLUNK_TOKEN###
  insecureSSL: "false"
  port: "###SPLUNK_PORT###"
image:
  pullPolicy: "Always"
traps:
  communities:
    2c:
      - public
      - homelab
  #usernameSecrets:
  #  - sc4snmp-hlab-sha-aes
  #  - sc4snmp-hlab-sha-des

  #loadBalancerIP: The IP address in the metallb pool
  loadBalancerIP: ###X.X.X.X###
worker:
  # There are 3 types of workers 
  trap:
    # replicaCount: number of trap-worker pods which consumes trap tasks
    replicaCount: 2
    # autoscaling: use it instead of replicaCount in order to make pods scalable by itself
#    autoscaling:
#      enabled: true
#      minReplicas: 2
#      maxReplicas: 40
#      targetCPUUtilizationPercentage: 80
  poller:
    # replicaCount: number of poller-worker pods which consumes polling tasks
    replicaCount: 2
    # autoscaling: use it instead of replicaCount in order to make pods scalable by itself
#    autoscaling:
#      enabled: true
#      minReplicas: 2
#      maxReplicas: 40
#      targetCPUUtilizationPercentage: 80
  sender:
    # replicaCount: number of sender-worker pods which consumes sending tasks
    replicaCount: 1
    # autoscaling: use it instead of replicaCount in order to make pods scalable by itself
#    autoscaling:
#      enabled: true
#      minReplicas: 2
#      maxReplicas: 40
#      targetCPUUtilizationPercentage: 80
  # udpConnectionTimeout: timeout in seconds for SNMP operations
  #udpConnectionTimeout: 5
  logLevel: "INFO"
scheduler:
  logLevel: "INFO"
#  profiles: |
#    generic_switch:
#      frequency: 60
#      varBinds:
#        - ['SNMPv2-MIB', 'sysDescr']
#        - ['SNMPv2-MIB', 'sysName', 0]
#        - ['IF-MIB']
#        - ['TCP-MIB']
#        - ['UDP-MIB']
poller:
 # usernameSecrets:
 #   - sc4snmp-hlab-sha-aes
 #   - sc4snmp-hlab-sha-des
 # inventory: |
 #   address,port,version,community,secret,securityEngine,walk_interval,profiles,SmartProfiles,delete
 #   10.0.0.1,,3,,sc4snmp-hlab-sha-aes,,600,,,
 #   10.0.0.199,,2c,public,,,600,,,True
 #   10.0.0.100,,3,,sc4snmp-hlab-sha-des,,600,,,
sim:
  # sim must be enabled if you want to use signalFx
  enabled: false
#  signalfxToken: BCwaJ_Ands4Xh7Nrg
#  signalfxRealm: us0
mongodb:
  pdb:
    create: true
  persistence:
    storageClass: "microk8s-hostpath"
  volumePermissions:
    enabled: true
```

`values.yaml` is being used during the installation process for configuring Kubernetes values.

### Configure Splunk Enterprise or Splunk Cloud Connection
Splunk Enterprise or Splunk Cloud connection is enabled by default, to disable Splunk Enterprise or Splunk Cloud `splunk.enabled` property must be set to `false`.
Additionally, connection parameters for Splunk Enterprise or Splunk Cloud needs to be set in `splunk` section: 

| Placeholder   | Description  | Example  | 
|---|---|---|
| ###SPLUNK_HOST###  | host address of splunk instance   | "i-08c221389a3b9899a.ec2.splunkit.io"  | 
| ###SPLUNK_PORT###  | port number of splunk instance   | "8088"  | 
| ###SPLUNK_TOKEN### | Splunk HTTP Event Collector token  | 450a69af-16a9-4f87-9628-c26f04ad3785  |
| ###X.X.X.X###  | SHARED IP address used for SNMP Traps   | 10.202.18.166  |

Other optional variables can be configured:

| variable | description | default |
| --- | --- | --- |
| splunk.protocol | port of splunk instance| https |
| splunk.insecure_ssl| is insecure ssl allowed | "true" |
| splunk.eventIndex | name of the events index | "netops" |
| splunk.metricsIndex | name of the metrics index | "netmetrics" |


### Configure Splunk Infrastructure Monitoring Connection
Splunk Infrastructure Monitoring is disabled by default, to enable Splunk Infrastructure Monitoring 
`sim.enabled` property must be set to `true`.
Additionally, connection parameters for Splunk Infrastructure Monitoring need to be set in `sim` section:

| variable | description | default |
| --- | --- | --- |
|signalfxToken | SIM token which can be use for ingesting date vi API | not set|
|signalfxRealm | Real of SIM | not set |

For more details please check [SIM Configuration](../configuration/sim-configuration.md)

### Install SC4SNMP
``` bash
microk8s helm3 install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
```

From now on, when editing SC4SNMP configuration, the configuration change must be
inserted in the corresponding section of `values.yaml`. For more details check [configuration](../configuration/deployment-configuration.md) section.

Use the following command to propagate configuration changes:
``` bash
microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
```

### Verify deployment
In a few minutes, all pods should be up and running. It can be verified with:
``` bash
microk8s kubectl get pods -n sc4snmp
```
Example output:
``` 
NAME                                                      READY   STATUS             RESTARTS      AGE
snmp-splunk-connect-for-snmp-scheduler-7ddbc8d75-bljsj        1/1     Running   0          133m
snmp-splunk-connect-for-snmp-worker-poller-57cd8f4665-9z9vx   1/1     Running   0          133m
snmp-splunk-connect-for-snmp-worker-sender-5c44cbb9c5-ppmb5   1/1     Running   0          133m
snmp-splunk-connect-for-snmp-worker-trap-549766d4-28qzh       1/1     Running   0          133m
snmp-mibserver-7f879c5b7c-hz9tz                               1/1     Running   0          133m
snmp-mongodb-869cc8586f-vvr9f                                 2/2     Running   0          133m
snmp-redis-master-0                                           1/1     Running   0          133m
snmp-splunk-connect-for-snmp-trap-78759bfc8b-79m6d            1/1     Running   0          99m
```

### Test SNMP Traps
- Test the Trap by logging into Splunk and confirming the presence of events
    in snmp `netops` and metrics in `netmetrics` index

-   Test the trap from a Linux system with SNMP installed. Replace the IP address 
    `10.0.101.22` with the shared IP address above

``` bash
apt update
apt-get install snmpd
snmptrap -v2c -c public 10.0.101.22 123 1.3.6.1.2.1.1.4 1.3.6.1.2.1.1.4 s test
```

-   Search Splunk: You should see one event per trap command with the host value of the
    test machine IP address

``` bash
index="netops" sourcetype="sc4snmp:traps"
```

### Test SNMP Poller
- Test the Poller by logging into Splunk and confirming the presence of events
    in snmp `netops` and metrics in `netmetrics` index

- Test the trap from a Linux system install snmpd.
    
``` bash
apt update
apt-get install snmpd
```

- To test SNMP poller, snmpd needs to be configured to listen on external IP. To enabled listening snmpd to external IP, 
in configuration file: `/etc/snmp/snmpd.conf` replace the IP address  `10.0.101.22` with the server IP address where snmpd is configured
`agentaddress  10.0.101.22,127.0.0.1,[::1]`. Restart snmpd by execute command:
``` bash
service snmpd stop
service snmpd start
```

- Configure SC4SNMP Poller to test add IP address which need to be poll. Add configuration entry in `value.yaml` file by 
replace the IP address `10.0.101.22` with the server IP address where snmpd were configured.
``` bash
poller:
  usernameSecrets:
    - sc4snmp-homesecure-sha-aes
    - sc4snmp-homesecure-sha-des
  inventory: |
    address,version,community,walk_interval,profiles,SmartProfiles,delete
    10.0.101.22,public,60,,,
```

- Load `values.yaml` file in SC4SNMP

``` bash
microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
```

-   Check-in Splunk
 
 Up to 1 min events appear in Splunk:

``` bash
index="netops" sourcetype="sc4snmp:event"
```
 Up to 1 min events appear in Splunk:
``` bash
| mpreview index="netmetrics" | search sourcetype="sc4snmp:metric"
```
