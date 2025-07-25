# Poller Configuration

Poller is a service which is responsible for querying 
SNMP devices using the SNMP GET and WALK functionalities. Poller executes two main types of tasks:

- The Walk task executes SNMP walk. SNMP walk is an SNMP application that uses SNMP GETNEXT requests to 
collect SNMP data from the network and infrastructure of SNMP-enabled devices, such as switches and routers. It is a time-consuming task,
which may overload the SNMP device when executed too often. It is used by the SC4SNMP to collect and push all OID values, which the provided ACL has access to. 
  
- The Get task is a lightweight task that queries a subset of OIDs defined by the customer. This task monitors OIDs, such as memory or CPU utilization.  

Poller has an `inventory`, which defines what and how often SC4SNMP has to poll.

### Poller configuration file

The poller configuration is kept in a `values.yaml` file in the `poller` section.
`values.yaml` is used during the installation process for configuring Kubernetes values.

See the following poller example configuration:
```yaml
poller:
  usernameSecrets:
   - sc4snmp-hlab-sha-aes
   - sc4snmp-hlab-sha-des
  logLevel: "WARN"
  inventory: |
    address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
    10.202.4.202,,2c,public,,,2000,,,
```

!!! info
    The header's line (`address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete`) is necessary for the correct execution of SC4SNMP. Do not remove it.

### IPv6 hostname resolution
When IPv6 is enabled and device is dual stack, the hostname resolution will try to resolve the name to the IPv6 address first, then to the IPv4 address.

### Define log level
The log level for poller can be set by changing the value for the key `logLevel`. The allowed values are: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` or `FATAL`. 
The default value is `INFO`.

### Define maxRepetitions
!!! info
    Released only in improved polling package.

The maxRepetitions is a parameter used in SNMP GetBulk call. It is responsible for controlling the
amount of variables in one request. 
```yaml
poller:
  maxRepetitions: 10
```
`maxRepetitions` variable is the amount of requested next oids in response for each of varbinds in one request sent.

For example:

The configured variables:
```yaml
poller:
  maxRepetitions: 2
```
The requested varbinds in one getBulk call:
```
IP-MIB.ipNetToMediaNetAddress
```

[![PDU Request Example](../../images/request_pdu_flow.png)](../../images/request_pdu_flow.png)

After third ResponsePDU the returned oids are out of scope for requested table, so the call is stopped. 
It can be spotted on diagram that response for `IP-MIB.ipNetToMediaNetAddress` includes 2 oids as `maxRepetition` was set to 2.

### Define usernameSecrets
Secrets are required to run SNMPv3 polling. To add v3 authentication details, create the k8s Secret object: [SNMPv3 Configuration](snmpv3-configuration.md), and put its name in `poller.usernameSecrets`.

### Append OID index part to the metrics

Not every SNMP metric object is structured with its index as a one of the field values. We can append the index part of OID with:

```yaml
poller:
  metricsIndexingEnabled: true
```

So the following change will make this metric object (derived from the OID `1.3.6.1.2.1.6.20.1.4.0.0.443`)

```
{
   frequency: 5
   metric_name:sc4snmp.TCP-MIB.tcpListenerProcess: 309
   mibIndex: 0.0.443
   profiles: generic_switch
}
```

out of this object:
```
{
   frequency: 5
   metric_name:sc4snmp.TCP-MIB.tcpListenerProcess: 309
   profiles: generic_switch
}
```

### Disable automatic polling of base profiles

There are [two profiles](https://github.com/splunk/splunk-connect-for-snmp/blob/main/splunk_connect_for_snmp/profiles/base.yaml) that are being polled by default, so that even without any configuration set up, you can see
the data in Splunk. You can disable it with the following `pollBaseProfiles` parameter:

```yaml
poller:
  pollBaseProfiles: false
```


### Configure inventory 
To update inventory, see [Update Inventory and Profile](#update-inventory).

The `inventory` section in `poller` has the following fields to configure:

| Field             | Description                                                                                                                                                                                                                             | Default | Required |
|-------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------|----------|
| `address`         | The IP address which SC4SNMP should collect data from, or name of the group of hosts. General information about groups can be found on the [Configuring Groups](configuring-groups.md) page.                                            |         | YES      |
| `port`            | SNMP listening port.                                                                                                                                                                                                                    | `161`   | NO       |
| `version`         | SNMP version, the allowed values are `1`, `2c`, or `3`.                                                                                                                                                                                 |         | YES      |
| `community`       | SNMP community string, this field is required when the `version` is `1` or `2c`.                                                                                                                                                        |         | NO       |
| `secret`          | The reference to the secret from `poller.usernameSecrets` that should be used to poll from the device.                                                                                                                                  |         | NO       |
| `security_engine` | The security engine ID required by SNMPv3. If it is not provided for version `3`, it will be autogenerated.                                                                                                                             |         | NO       |
| `walk_interval`   | The interval in seconds for SNMP walk. This value needs to be between `1800` and `604800`.                                                                                                                                              | `42000` | NO       |
| `profiles`        | A list of SNMP profiles used for the device. More than one profile can be added by a semicolon separation, for example, `profile1;profile2`. For more information about profiles, see [Profile Configuration](../configuring-profiles). |         | NO       |
| `smart_profiles`  | Enables smart profiles. Its allowed values are `true` or `false`.                                                                                                                                                                       | `true`  | NO       |
| `delete`          | A flag that defines if the inventory should be deleted from the scheduled tasks for WALKs and GETs. Its allowed value are `true`or `false`. The default value is `false`.                                                               | `false` | NO       |

See the following example:
```yaml
poller:
    inventory: |
      address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
      10.202.4.202,,2c,public,,,2000,my_profile1,,
      example_group_1,,2c,public,,,2000,my_profile2;my_profile3,,
```


### Update Inventory
Adding new devices for `values.yaml` is resource expensive, and can impact performance. As it interacts with hardware networking devices,
the updating process requires several checks before applying changes. SC4SNMP was designed to prevent changes in inventory tasks 
more often than every 5 minutes.

To apply inventory changes in `values.yaml`, the following steps need to be executed:

1. Edit `values.yaml` 
2. Check if the inventory pod is still running using the following execute command:
   
```shell
microk8s kubectl -n sc4snmp get pods | grep inventory
```
   
If the command return pods, wait and continue to execute the command again, until the inventory job finishes. 

If you really need to apply changes immediately, you can get around the limitation by deleting the inventory job using the following command:

```shell
microk8s kubectl delete job/snmp-splunk-connect-for-snmp-inventory -n sc4snmp
```

After running this command, you can proceed with upgrading without a need to wait.
   
3. Run upgrade command :

```shell
microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
```

!!! info
    If you decide to change the frequency of the profile without changing the inventory data, the change will be reflected after 
    the next walk process for the host. The walk happens every `walk_interval`, or during any change in inventory.

#### Upgrade with the csv file

You can update inventory by making changes outside of the `values.yaml`. It can be put into a separate csv file and upgraded
using `--set-file poller.inventory=<path_to_file>`.

See the following example of an CSV file configuration:

```csv
address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
10.202.4.202,,2c,public,,,3000,my_profile,,
```

See the following example of an upgrade command with a CSV file:

```shell
microk8s helm3 upgrade --install snmp -f values.yaml --set-file poller.inventory=inventory.csv splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
```
