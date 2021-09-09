# SC4SNMP Helm installation

### Add SC4SNMP repository
```
microk8s helm3 repo add splunk-connect-for-snmp https://splunk.github.io/splunk-connect-for-snmp
microk8s repo update
```
Now package should be visible in helm3 search command result:
```
splunker@ip-10-202-7-16:~/new_helm$ microk8s helm3 search repo snmp
NAME                                    	CHART VERSION	APP VERSION	DESCRIPTION                
splunk-connect-for-snmp/snmp-installer  	0.1.0        	1.16.0     	A Helm chart for Kubernetes
```

### Download and modify values.yaml file
```
microk8s helm3 inspect values splunk-connect-for-snmp/snmp-installer > values.yaml
```
The most important variables to update are:

| Placeholder   | Description  | Example  | 
|---|---|---|
| ###SPLUNK_HOST###  | host address of splunk instance   | i-08c221389a3b9899a.ec2.splunkit.io  | 
| ###SPLUNK_TOKEN### | Splunk HTTP Event Collector token  | 450a69af-16a9-4f87-9628-c26f04ad3785  |
| ###X.X.X.X###  | SHARED IP address used for SNMP Traps   | 10.202.18.166  |

