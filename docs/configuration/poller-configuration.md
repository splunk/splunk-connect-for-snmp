#Poller Configuration
The instruction contains configuration documentation for Poller. Poller is a service which is responsible for querying 
SNMP devices using SNMP GET, SNMP WALK functionality. Poller executes two main types of tasks:
- Walk task execute SNMP walk. SNMP walk is an SNMP application that uses SNMP GETNEXT requests to 
collect SNMP data from network and infrastructure SNMP-enabled devices, such as switches and routers. It is a time-consuming task,
which may overload the SNMP device when executing too often. It is used by SC4SNMP to collect and push all OIDs values which provided ACL has access to. 
- Get task - It is a lightweight task whose goal is to query a subset of OIDs defined by the customer. The task is dedicated to enabling monitoring of the most important OIDs with high frequency like memory or CPU utilization.  

### Poller configuration file

Poller configuration is kept in `values.yaml` file in section poller.
`values.yaml` is being used during the installation process for configuring Kubernetes values.

Poller example configuration:
```yaml
poller:
  logLevel: "WARN"
  inventory: |
    address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
    10.202.4.202,,2c,public,,,2000,,,
```

NOTE: header's line (`address,port,version,community`) is necessary for the correct execution of SC4SNMP. Do not remove it.

### Define log level
Log level for trap can be set by changing the value for key `logLevel`. Allowed values are: `DEBUG`, `INFO`, `WARNING`, `ERROR`. 
The default value is `WARNING`

### Configure inventory 
To update inventory follow instruction: [Update Inventory and Profile](../deployment-configuration/#update-inventory-and-profile) 
`inventory` section in `poller` enable to configure inventory for polling data:

 - `address` [REQUIRED] - IP address which SC4SNMP should connect to collect data from.
 - `port` [OPTIONAL] - SNMP listening port. Default value `161`.
 - `version` [REQUIRED] - SNMP version, allowed values: `1`, `2c` or `3`
 - `community` [OPTIONAL] - SNMP community string, filed is required when `version` is `1` or `2c`
 - `secret` [OPTIONAL] - usernameSecrets define which secrets in "Secret" objects in k8s should be use, as a value it need to put 
 name of "Secret" objects. Field is required when `version` is `3`. More information how to define "Secrets" object for SNMPv3 can be found 
 in [SNMPv3 Configuration](snmpv3-configuration.md)
 - `security_engine` [OPTIONAL] - Security engine required by SNMPv3. Field is required when `version` is `3`. 
 - `walk_interval` [OPTIONAL] - Define interval in second for SNMP walk, default value `42000`
 - `profiles` [OPTIONAL] - list of SNMP profiles which need to be used for device. More than one profile can be added by semicolon 
separation eg. `profiale1;profile2`. More about profile in [Profile Configuration](../scheduler-configuration/#configure-profile)
 - `smart_profiles` [OPTIONAL] - enabled SmartProfile, default value true. Allowed value: `true`, `false`. Default value is `true` 
 - `delete` [OPTIONAL] - flags which define if inventory should be deleted from scheduled tasks for walk and gets. 
Allowed value: `true`, `false`. Default value is `false`.

Example:
```yaml
poller:
    inventory: |
      address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
      10.202.4.202,,2c,public,,,2000,,,
```


