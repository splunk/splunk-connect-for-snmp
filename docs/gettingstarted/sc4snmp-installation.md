# SC4SNMP Helm installation

### Add SC4SNMP repository
```
microk8s helm3 repo add splunk-connect-for-snmp https://splunk.github.io/splunk-connect-for-snmp
microk8s helm3 repo update
```
Now package should be visible in `helm3` search command result:
```
splunker@ip-10-202-7-16:~/new_helm$ microk8s helm3 search repo snmp
NAME                                  	CHART VERSION	APP VERSION	DESCRIPTION                     
splunk-connect-for-snmp/snmp-installer	0.1.1        	1.16.0     	A Helm chart for Splunk for SNMP
```

### Download and modify values.yaml file
```
microk8s helm3 inspect values splunk-connect-for-snmp/snmp-installer > values.yaml
```
Variables required to be updated:

| Placeholder   | Description  | Example  | 
|---|---|---|
| ###SPLUNK_HOST###  | host address of splunk instance   | i-08c221389a3b9899a.ec2.splunkit.io  | 
| ###SPLUNK_PORT### | port of splunk instance | 8088 |
| ###INSECURE_SSL### | is insecure ssl allowed | "true" |
| ###SPLUNK_TOKEN### | Splunk HTTP Event Collector token  | 450a69af-16a9-4f87-9628-c26f04ad3785  |
| ###CLUSTER_NAME### | name of the cluster | "foo" |
| ###X.X.X.X###  | SHARED IP address used for SNMP Traps   | 10.202.18.166  |

### Install SC4SNMP
```yaml
microk8s helm3 install snmp -f values.yaml splunk-connect-for-snmp/snmp-installer --namespace=sc4snmp --create-namespace
```

### Verify deployment
In a few minutes all of the pods should be up and running. It can be verified with:
```yaml
$ microk8s kubectl get pods -n sc4snmp
NAME                                 READY   STATUS    RESTARTS   AGE
sc4snmp-traps-569547fcb4-9gxd5       1/1     Running   0          19m
sc4snmp-worker-65b4c6df9d-bmgrj      1/1     Running   0          19m
sc4snmp-otel-6b65b45b84-frj6x        1/1     Running   0          19m
sc4snmp-mib-server-9f765c956-rbm7z   1/1     Running   0          19m
sc4snmp-scheduler-5bb8d5fd9c-p7j86   1/1     Running   1          19m
sc4snmp-mongodb-85f6c9c575-vhfr9     2/2     Running   0          19m
sc4snmp-rabbitmq-0                   1/1     Running   0          19m
```
