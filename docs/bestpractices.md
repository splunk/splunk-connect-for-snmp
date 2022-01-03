# Debug Splunk Connect for SNMP

### Check when SNMP WALK was executed last time for device
1. [Configure SCK](gettingstarted/sck-installation.md)
2. Go to your Splunk and execute search: `index="em_logs"   "Sending due task" "sc4snmp;<IP_ADDRESS>;walk"` 
and replace <IP_ADDRESS> by IP Address which you are intrested. 

### Uninstall Splunk Connect for SNMP
To uninstall SC4SNMP run following commands:

```shell script
 microk8s helm3 uninstall snmp -n sc4snmp
 microk8s kubectl delete pvc --all -n sc4snmp
```

### Installing Splunk Connect for SNMP on Linux RedHat 
Installation of RedHat may blocking ports required by microk8s. Installing microk8s on RedHat 
required to check if firewall is not blocking any of [required microk8s ports](https://microk8s.io/docs/ports). 