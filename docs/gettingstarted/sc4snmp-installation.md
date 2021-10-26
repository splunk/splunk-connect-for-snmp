# SC4SNMP Helm installation

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
NAME                                  	CHART VERSION	APP VERSION	DESCRIPTION                     
splunk-connect-for-snmp/snmp-installer	0.1.1        	1.16.0     	A Helm chart for Splunk for SNMP
```

### Download and modify deployment_values.yaml and config_values.yaml files
```
curl -o ~/deployment_values.yaml https://raw.githubusercontent.com/splunk/splunk-connect-for-snmp/develop/deploy-helm/snmp-installer/deployment_values.yaml
curl -o ~/config_values.yaml https://raw.githubusercontent.com/splunk/splunk-connect-for-snmp/develop/deploy-helm/snmp-installer/config_values.yaml
```

`deployment_values.yaml` is being used during the installation process for configuring kubernetes values.

`config_values.yaml` contains configuration of SC4SNMP.


Variables required to be updated in `deployment_values.yaml`:

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
| splunk: insecure_ssl| is insecure ssl allowed | "false" |
| splunk: cluster_name | name of the cluster | "foo" |

### Install SC4SNMP
``` bash
microk8s helm3 install snmp -f deployment_values.yaml -f config_values.yaml splunk-connect-for-snmp/snmp-installer --namespace=sc4snmp --create-namespace
```
From now on, when editing SC4SNMP configuration, the configuration change must be
inserted in the corresponding section of `config_values.yaml`. For more details check [configuration](../configuration.md) section.

Use the following command to propagate configuration changes:
``` bash
microk8s helm3 upgrade --install snmp -f deployment_values.yaml -f config_values.yaml splunk-connect-for-snmp/snmp-installer --namespace=sc4snmp --create-namespace
```
### Verify deployment
In a few minutes, all pods should be up and running. It can be verified with:
``` bash
microk8s kubectl get pods -n sc4snmp
```
Example output:
``` 
NAME                                 READY   STATUS    RESTARTS   AGE
sc4snmp-traps-569547fcb4-9gxd5       1/1     Running   0          19m
sc4snmp-worker-65b4c6df9d-bmgrj      1/1     Running   0          19m
sc4snmp-otel-6b65b45b84-frj6x        1/1     Running   0          19m
sc4snmp-mib-server-9f765c956-rbm7z   1/1     Running   0          19m
sc4snmp-scheduler-5bb8d5fd9c-p7j86   1/1     Running   1          19m
sc4snmp-mongodb-85f6c9c575-vhfr9     2/2     Running   0          19m
sc4snmp-rabbitmq-0                   1/1     Running   0          19m
```
