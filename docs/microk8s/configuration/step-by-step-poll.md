# An example of a polling scenario

In the following example, there are 4 hosts you want to poll from: 

1. `10.202.4.201:161`
2. `10.202.4.202:161`
3. `10.202.4.203:161`
4. `10.202.4.204:163`
   
To retrieve data from the device efficiently, first determine the specific data needed. Instead of walking through 
the entire `1.3.6.1`, limit the walk to poll only the necessary data. Configure the `IF-MIB` family for interfaces and 
the `UCD-SNMP-MIB` for CPU-related statistics. In the `scheduler` section of `values.yaml`, define the target group and 
establish the polling parameters, known as the profile, to gather the desired data precisely. See the following example: 

```yaml
scheduler:
  logLevel: "INFO"
  profiles: |
    small_walk:
      condition:
        type: "walk"
      varBinds:
        - ["IF-MIB"]
        - ["UCD-SNMP-MIB"]
    switch_profile:
      frequency: 60
      varBinds:
        - ["IF-MIB", "ifDescr"]
        - ["IF-MIB", "ifAdminStatus"]
        - ["IF-MIB", "ifOperStatus"]
        - ["IF-MIB", "ifName"]
        - ["IF-MIB", "ifAlias"]
        - ["IF-MIB", "ifIndex"]
        - ["IF-MIB", "ifInDiscards"]
        - ["IF-MIB", "ifInErrors"]
        - ["IF-MIB", "ifInOctets"]
        - ["IF-MIB", "ifOutDiscards"]
        - ["IF-MIB", "ifOutErrors"]
        - ["IF-MIB", "ifOutOctets"]
        - ["IF-MIB", "ifOutQLen"]
        - ["UCD-SNMP-MIB"]
  groups: |
    switch_group:
      - address: 10.202.4.201
      - address: 10.202.4.202
      - address: 10.202.4.203
      - address: 10.202.4.204
        port: 163
```

It is required to pass the proper instruction of what to do for the SC4SNMP instance. To do this, append a new row
to `poller.inventory`:

```yaml
poller:
  logLevel: "WARN"
  inventory: |
    address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
    switch_group,,2c,public,,,2000,small_walk;switch_profile,,
```

The provided example configuration will make:

1. Walk devices from `switch_group` with `IF-MIB` and `UCD-SNMP-MIB` every 2000 seconds
2. Poll specific `IF-MIB` fields and the whole `UCD-SNMP-MIB` every 60 seconds

Note: You can also limit the walk profile even more if you want to enhance the performance.

It makes sense to put the textual values in the walk that aren't required to be constantly monitored, and monitor only the metrics
you're interested in:

```
small_walk:
  condition:
    type: "walk"
  varBinds:
    - ["IF-MIB", "ifDescr"]
    - ["IF-MIB", "ifAdminStatus"]
    - ["IF-MIB", "ifOperStatus"]
    - ["IF-MIB", "ifName"]
    - ["IF-MIB", "ifAlias"]
    - ["IF-MIB", "ifIndex"]
switch_profile:
  frequency: 60
  varBinds:
    - ["IF-MIB", "ifInDiscards"]
    - ["IF-MIB", "ifInErrors"]
    - ["IF-MIB", "ifInOctets"]
    - ["IF-MIB", "ifOutDiscards"]
    - ["IF-MIB", "ifOutErrors"]
    - ["IF-MIB", "ifOutOctets"]
    - ["IF-MIB", "ifOutQLen"]
```

Afterwards, every metric object will be enriched with the textual values gathered from a walk process. See [here](snmp-data-format.md) for more information about SNMP format.


Now you're ready to reload SC4SNMP. Run the following `helm3 upgrade` command:

```yaml
microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
```

See the new pod with the following `Running` -> `Completed` state command:

```yaml
microk8s kubectl get pods -n sc4snmp -w
```

See the following example output:
```yaml
NAME                                                          READY   STATUS    RESTARTS   AGE
snmp-splunk-connect-for-snmp-worker-sender-5bc5cf864b-cwmfw   1/1     Running   0          5h52m
snmp-splunk-connect-for-snmp-worker-poller-76dcfb5896-d55pd   1/1     Running   0          5h52m
snmp-splunk-connect-for-snmp-worker-trap-68fb6476db-zl9rb     1/1     Running   0          5h52m
snmp-mibserver-58b558f5b4-zqf85                               1/1     Running   0          5h52m
snmp-splunk-connect-for-snmp-scheduler-57c5878444-k4qv4       1/1     Running   0          5h52m
snmp-splunk-connect-for-snmp-worker-poller-76dcfb5896-bzgrm   1/1     Running   0          5h52m
snmp-splunk-connect-for-snmp-trap-6cb76fcb49-l62f9            1/1     Running   0          5h52m
snmp-splunk-connect-for-snmp-trap-6cb76fcb49-d7c88            1/1     Running   0          5h52m
snmp-mongodb-869cc8586f-kw67q                                 2/2     Running   0          5h52m
snmp-redis-master-0                                           1/1     Running   0          5h52m
snmp-splunk-connect-for-snmp-inventory-g4bs7                  1/1     Running   0          3s
snmp-splunk-connect-for-snmp-inventory-g4bs7                  0/1     Completed   0          5s
snmp-splunk-connect-for-snmp-inventory-g4bs7                  0/1     Completed   0          6s
snmp-splunk-connect-for-snmp-inventory-g4bs7                  0/1     Completed   0          7s
```

Check the pod's logs to make sure everything was reloaded correctly, using the following command:

```yaml
microk8s kubectl logs -f snmp-splunk-connect-for-snmp-inventory-g4bs7  -n sc4snmp
```

See the following example output:

```yaml
Successfully connected to redis://snmp-redis-headless:6379/0
Successfully connected to redis://snmp-redis-headless:6379/1
Successfully connected to mongodb://snmp-mongodb:27017
Successfully connected to http://snmp-mibserver/index.csv
{"message": "Loading inventory from /app/inventory/inventory.csv", "time": "2022-09-05T14:30:30.605420", "level": "INFO"}
{"message": "New Record address='10.202.4.201' port=161 version='2c' community='public' secret=None security_engine=None walk_interval=2000 profiles=['switch_profile'] smart_profiles=True delete=False", "time": "2022-09-05T14:30:30.607641", "level": "INFO"}
{"message": "New Record address='10.202.4.202' port=161 version='2c' community='public' secret=None security_engine=None walk_interval=2000 profiles=['switch_profile'] smart_profiles=True delete=False", "time": "2022-09-05T14:30:30.607641", "level": "INFO"}
{"message": "New Record address='10.202.4.203' port=161 version='2c' community='public' secret=None security_engine=None walk_interval=2000 profiles=['switch_profile'] smart_profiles=True delete=False", "time": "2022-09-05T14:30:30.607641", "level": "INFO"}
{"message": "New Record address='10.202.4.204' port=163 version='2c' community='public' secret=None security_engine=None walk_interval=2000 profiles=['switch_profile'] smart_profiles=True delete=False", "time": "2022-09-05T14:30:30.607641", "level": "INFO"}
```

In some time (depending on how long the walk takes), we'll see events using the following query:

```yaml
| mpreview index=netmetrics | search profiles=switch_profile
```

When groups are used, we can also use querying by the group name, for example:

```yaml
| mpreview index=netmetrics | search group=switch_group
```

Querying by profiles/group in Splunk is only possible in the metrics index. Every piece of data being sent
by SC4SNMP is formed based on the MIB file's definition of the SNMP object's index. The object is forwarded to an event index only if it doesn't have any metric value inside.

The following is a Splunk `raw` metrics example:

```json
{
   "frequency":"60",
   "group":"switch_group",
   "ifAdminStatus":"up",
   "ifAlias":"1",
   "ifDescr":"lo",
   "ifIndex":"1",
   "ifName":"lo",
   "ifOperStatus":"up",
   "ifPhysAddress":"1",
   "ifType":"softwareLoopback",
   "profiles":"switch_profile",
   "metric_name:sc4snmp.IF-MIB.ifInDiscards":21877,
   "metric_name:sc4snmp.IF-MIB.ifInErrors":21840,
   "metric_name:sc4snmp.IF-MIB.ifInNUcastPkts":14152789,
   "metric_name:sc4snmp.IF-MIB.ifInOctets":1977814270,
   "metric_name:sc4snmp.IF-MIB.ifInUcastPkts":220098191,
   "metric_name:sc4snmp.IF-MIB.ifInUnknownProtos":1488029,
   "metric_name:sc4snmp.IF-MIB.ifLastChange":124000001,
   "metric_name:sc4snmp.IF-MIB.ifMtu":16436,
   "metric_name:sc4snmp.IF-MIB.ifOutDiscards":21862,
   "metric_name:sc4snmp.IF-MIB.ifOutErrors":21836,
   "metric_name:sc4snmp.IF-MIB.ifOutNUcastPkts":14774727,
   "metric_name:sc4snmp.IF-MIB.ifOutOctets":1346799625,
   "metric_name:sc4snmp.IF-MIB.ifOutQLen":4294967295,
   "metric_name:sc4snmp.IF-MIB.ifOutUcastPkts":74003841,
   "metric_name:sc4snmp.IF-MIB.ifSpeed":10000000
}
```

or

```json
{
   "frequency":"60",
   "group":"switch_group",
   "laNames":"Load-1",
   "profiles":"switch_profile",
   "metric_name:sc4snmp.UCD-SNMP-MIB.laIndex":1
}
```
