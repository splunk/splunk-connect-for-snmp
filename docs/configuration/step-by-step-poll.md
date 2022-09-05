# Example polling scenario

We have 4 hosts we want to poll from:

1. `10.202.4.201:161`
2. `10.202.4.202:161`
3. `10.202.4.203:161`
4. `10.202.4.204:163`
   
Let's say, that we're interested mostly in information about interfaces and some CPU related data. For this purposes,
we need to configure `IF-MIB` family for interfaces, and `UCD-SNMP-MIB` for the CPU.

We'll do two things under `scheduler` section: define the group from which we want to poll, and the profile of what exactly will be polled:

```yaml
scheduler:
  logLevel: "INFO"
  profiles: |
    switch_profile:
      frequency: 60
      varBinds:
        - ['IF-MIB']
        - ['UCD-SNMP-MIB']
  groups: |
    switch_group:
      - address: 10.202.4.201
      - address: 10.202.4.202
      - address: 10.202.4.203
      - address: 10.202.4.204
        port: 163
```

Then we need to pass the proper instruction of what to do for SC4SNMP instance. This can be done by appending a new row
to `poller.inventory`:

```yaml
poller:
  logLevel: "WARN"
  inventory: |
    address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
    switch_group,,2c,public,,,2000,switch_profile,,
```

Now we're ready to reload SC4SNMP. We run the `helm3 upgrade` command:

```yaml
microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
```

We should see the new pod with `Running` -> `Completed` state:

```yaml
microk8s kubectl get pods -n sc4snmp -w
```

Example output:
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

We can check the pod's logs to make sure everything was reloaded right, with:

```yaml
microk8s kubectl logs -f snmp-splunk-connect-for-snmp-inventory-g4bs7  -n sc4snmp
```

Example output:

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

In some time (depending of how long does the walk takes), we'll see events under:

```yaml
| mpreview index=netmetrics | search profiles=switch_profile
```

query in Splunk. When groups are used, we can also use querying by the group name:

```yaml
| mpreview index=netmetrics | search group=switch_group
```

Keep in mind, that querying by profiles/group in Splunk is only possible in metrics index. Every piece of data being sent
by SC4SNMP is formed based on MIB file's definition of the SNMP object's index. The object is forwarded to an event index only if it doesn't have any metric value inside.
