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
  logLevel: "WARN"
  inventory: |
    address,port,version,community,secret,securityEngine,walk_interval,profiles,SmartProfiles,delete
    10.202.4.202,,2c,public,,,2000,,,
```

### Define log level
Log level for trap can be set by changing value for key `logLevel`. Allowed value are: `DEBUG`, `INFO`, `WARNING`, `ERROR`. 
Default value is `WARNING`

### Configure inventory 
`inventory` section in `poller` enable to configure inventory for polling data:

 - `address` [REQUIRED] - IP address which SC4SNMP should connect to collect data from.
 - `port` [OPTIONAL] - SNMP listening port. Default value `161`.
 - `version` [REQUIRED] - SNMP version, allowed values: `1`, `2c` or `3`
 - `community` [OPTIONAL] - SNMP community string, filed is required when `version` is `1` or `2c`
 - `secret` [OPTIONAL] - usernameSecrets define which secrets in "Secret" objects in k8s should be use, as a value it need to put 
 name of "Secret" objects. Field is required when `version` is `3`. More information how to define "Secrets" object for SNMPv3 can be found 
 in [SNMPv3 Configuration](snmpv3-configuration.md)
 - `securityEngine` [OPTIONAL] - Security engine required by SNMPv3. Field is required when `version` is `3`. 
 - `walk_interval` [OPTIONAL] - Define interval in second for SNMP walk, default value `42000`
 - `profiles` [OPTIONAL] - list of SNMP profiles which need to be used for device. More than one profile can be added by semicolon 
separation eg. `profiale1;profile2`. More about profile in [Profile Configuration](../scheduler-configuration/#configure-profile)
 - `SmartProfiles` [OPTIONAL] - enabled SmartProfile, default value true. Allowed value: `true`, `false`. Default value is `true` 
 - `delete` [OPTIONAL] - flags which define if inventory should be deleted from scheduled tasks for walk and gets. 
Allowed value: `true`, `false`. Default value is `false`.

Example:
```yaml
poller:
    inventory: |
      address,port,version,community,secret,securityEngine,walk_interval,profiles,SmartProfiles,delete
      10.202.4.202,,2c,public,,,2000,,,
```


