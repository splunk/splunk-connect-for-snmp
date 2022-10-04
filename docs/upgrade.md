# Upgrading SC4SNMP

## Upgrade to the latest version
To upgrade SC4SNMP to the latest version, simply run the following command:

```yaml
microk8s helm3 repo update
```

Afterwards, run:

```yaml
microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
```

SC4SNMP will be upgraded to the newest version. You can see the latest version after hitting the command:
```yaml
microk8s helm3 search repo snmp
```

The output looks like that:

```
NAME                                           	CHART VERSION	APP VERSION	DESCRIPTION                           
splunk-connect-for-snmp/splunk-connect-for-snmp	1.6.2        	1.6.2      	A Helm chart for SNMP Connect for SNMP
```

So in this case, the latest version is `1.6.2` and it will be installed after `helm3 upgrade` command.


## Upgrade to a specific version

Alternatively, you can install one of the previous versions, or a development one. You can list all the previous versions with:

```yaml
microk8s helm3 search repo snmp --versions
```

And all the development versions:

```yaml
microk8s helm3 search repo snmp --devel
```

To upgrade your SC4SNMP instance to any of the listed versions, run `helm3 upgrade` with the `--version` flag:


```yaml
microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace --version <VERSION>
```

For example:

```yaml
microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace --version 1.6.3-beta.13
```
