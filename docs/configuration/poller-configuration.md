#Poller Configuration
Instruction contains configuration documentation for Poller. Poller is a service which is responsible for quering 
SNMP devices using SNMP GET, SNMP WALK functionality. Poller executes two main type of tasks tasks:
- Walk task execute SNMP walk. SNMP walk is an SNMP application that uses SNMP GETNEXT requests to 
collect SNMP data from network and infrastructure SNMP-enabled devices, such as switches and routers. It is time consuming task,
which may overload SNMP device when execute too often. It is use by SC4SNMP to callect and push all OIDs values which provided ACL has access to. 
- Get task - It is light weight task which goal is to query subset of OIDs defined by customer. Task is dedicated 
to enabled monitoring of most important OIDs with high frequency like memory or CPU utilisation.  

### Poller configuration file

Poller configuration is keep in `values.yaml` file in section poller.  To downland example file execute command:
```
curl -o ~/values.yaml https://raw.githubusercontent.com/splunk/splunk-connect-for-snmp/develop/values.yaml
```
`values.yaml` is being used during the installation process for configuring kubernetes values.

Poller example configuration:
```yaml
poller:
  usernameSecrets:
    - sc4snmp-homesecure-sha-aes
    - sc4snmp-homesecure-sha-des
  inventory: |
    address,version,community,walk_interval,profiles,SmartProfiles,delete
    10.202.4.202,2c,public,60,,,
```

### Configure inventory 
Inventory key in poller enable to configure inventory for polling data:
address - IP address which SC4SNMP should connect to collect data from.
version - SNMP version, values allowed: 1, 2c, 3
community - SNMP community string
walk_interval - it is interval how often SNMP walk should be executed, default value 600 second <TO_DO check default value>
profiles - list of SNMP profiles for more information please check <TO_DO add link to profiles configuation>
 default value>
SmartProfiles - list of SC4SNMP SmartProfiles for more information please check <TO_DO add link to SmartProfiles configuation>
delete - flags which define if data should be deleted from scheduled tasks for walk and gets. Allowed value true, false.
default value is false <TO_DO check with Pawel>

Example:
```yaml
poller:
    inventory: |
      address,version,community,walk_interval,profiles,SmartProfiles,delete
      10.202.4.202,2c,public,60,,,
```

### Configure user secrets for SNMPv3 
usernameSecrets key in poller enable configure SNMPv3 secrets for polling data. usernameSecrets define which secrets 
in "Secret" objects in k8s should be use, as a value it need to put name of "Secret" objects. 
More information how to define "Secrets" object for SNMPv3 can be found in <TO_DO link to V3 secrets>

Example:
```yaml
poller:
    usernameSecrets:
      - sc4snmp-homesecure-sha-aes
      - sc4snmp-homesecure-sha-des
```   


