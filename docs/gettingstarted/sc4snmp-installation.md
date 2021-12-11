# SC4SNMP Helm installation

The basic installation process and configuration used in this section are typical 
for single node non HA deployments and do not have resource requests and limits.
See the configuration sections for mongo, rabbitmq, scheduler, worker, and traps for guidance
on production configuration.

### Add SC4SNMP repository
```
microk8s helm3 repo add splunk-connect-for-snmp https://splunk.github.io/splunk-connect-for-snmp
microk8s helm3 repo update
```
Now the package should be visible in `helm3` search command result:
``` bash
microk8s helm3 search repo snmp --devel 
```
Example output:
``` 
NAME                                           	CHART VERSION 	APP VERSION   	DESCRIPTION                           
splunk-connect-for-snmp/splunk-connect-for-snmp	0.11.0-beta.22	0.11.0-beta.22	A Helm chart for SNMP Connect for SNMP
```

### Download and modify values.yaml
```yaml
splunk:
  protocol: https
  host: ###SPLUNK_HOST###
  token: ###SPLUNK_TOKEN###
  insecureSSL: "false"
  port: "###SPLUNK_PORT###"
  clusterName: my-cluster
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
  loadBalancerIP: 10.1.0.1
worker:
  # replicas: Number of replicas for worker container should two or more
  #replicaCount: 2
  logLevel: "DEBUG"
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
mongodb:
  pdb:
    create: true
  persistence:
    storageClass: "openebs-hostpath"
  volumePermissions:
    enabled: true
rabbitmq:
  pdb:
    create: true
  replicaCount: 1
  persistence:
    enabled: true
    storageClass: "openebs-hostpath"
  volumePermissions:
    enabled: true
```

`values.yaml` is being used during the installation process for configuring kubernetes values.


| Placeholder   | Description  | Example  | 
|---|---|---|
| ###SPLUNK_HOST###  | host address of splunk instance   | "i-08c221389a3b9899a.ec2.splunkit.io"  | 
| ###SPLUNK_PORT###  | port number of splunk instance   | "8088"  | 
| ###SPLUNK_TOKEN### | Splunk HTTP Event Collector token  | 450a69af-16a9-4f87-9628-c26f04ad3785  |
| ###X.X.X.X###  | SHARED IP address used for SNMP Traps   | 10.202.18.166  |

Other variables to update in case you want to:

| variable | description | default |
| --- | --- | --- |
| splunk: protocol | port of splunk instance| https |
| splunk: insecure_ssl| is insecure ssl allowed | "true" |
| splunk: cluster_name | name of the cluster | "foo" |

### Install SC4SNMP
``` bash
microk8s helm3 install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace --version <VERSION_TAG>
```
| variable | description | default |
|---|---|---|
|VERSION_TAG| is a tag of build eg. 0.11.0-beta.22 | none|

From now on, when editing SC4SNMP configuration, the configuration change must be
inserted in the corresponding section of `values.yaml`. For more details check [configuration](../configuration/deployment-configuration.md) section.

Use the following command to propagate configuration changes:
``` bash
microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace --version <VERSION_TAG>
```
| variable | description | default |
|---|---|---|
|VERSION_TAG| is a tag of build eg. 0.11.0-beta.22 | none|

### Verify deployment
In a few minutes, all pods should be up and running. It can be verified with:
``` bash
microk8s kubectl get pods -n sc4snmp
```
Example output:
``` 
NAME                                                      READY   STATUS             RESTARTS      AGE
snmp-splunk-connect-for-snmp-worker-66685fcb6d-f6rxb      1/1     Running            0             6m4s
snmp-splunk-connect-for-snmp-scheduler-6586488d85-t6j5d   1/1     Running            0             6m4s
snmp-mongodb-arbiter-0                                    1/1     Running            0             6m4s
snmp-mibserver-6f575ddb7d-mmkmn                           1/1     Running            0             6m4s
snmp-mongodb-0                                            2/2     Running            0             6m4s
snmp-mongodb-1                                            2/2     Running            0             4m58s
snmp-rabbitmq-0                                           1/1     Running            0             6m4s
snmp-splunk-connect-for-snmp-traps-54f79b945d-bmbg7       1/1     Running            0             6m4s
```

### Test SNMP Traps
- Test the Trap by logging into Splunk and confirm the presence of events
    in snmp `netops` and metrics in `netmetrics` index

-   Test the trap from a linux system with SNMP installed. Replace the IP address 
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
- Test the Poller by logging into Splunk and confirm the presence of events
    in snmp `netops` and metrics in `netmetrics` index

- Test the trap from a linux system install snmpd.
    
``` bash
apt update
apt-get install snmpd
```

- To test snmp poller, snmpd need to be configure to listening on external IP. To enabled listening snmpd to external IP, 
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

- Load `value.yaml` file in SC4SNMP

``` bash
microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace --version <VERSION_TAG>
```
| variable | description | default |
|---|---|---|
|VERSION_TAG| is a tag of build eg. 0.11.0-beta.22 | none|

-   Check in Splunk
 
 Up to 1 min events appear in Splunk:

``` bash
index="netops" sourcetype="sc4snmp:event"
```
 Up to 1 min events appear in Splunk:
``` bash
| mpreview index="netmetrics" | search sourcetype="sc4snmp:metric"
```

