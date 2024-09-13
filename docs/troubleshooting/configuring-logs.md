## Configuring SC4SNMP loglevel

SC4SNMP loglevel can be configured in `values.yaml` file. The default `logLevel` for all components is `INFO`, other 
possible levels to set are `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` or `FATAL`. To change 
the `logLevel` for a specific component, add the following configuration to `values.yaml`:

```yaml
worker:
    logLevel: "DEBUG"
```

And redeploy SC4SNMP. 

`LogLevel` configuration can be set for `worker`, `poller`, `scheduler` and `traps`.

## Accessing SC4SNMP logs 

SC4SNMP logs can be browsed in Splunk in `em_logs` index, provided that [sck-otel](../gettingstarted/sck-installation.md)
is installed. Logs can be also accessed directly in kubernetes using terminal.

### Accessing logs via Splunk
If [sck-otel](../gettingstarted/sck-installation.md) is installed, browse `em_logs` index. Logs can be further filtered 
for example by the sourcetype field. Example search command to get logs from poller:
```
index=em_logs sourcetype="kube:container:splunk-connect-for-snmp-worker-poller"
```

### Accessing logs in kubernetes
To access logs directly in kubernetes, first run `microk8s kubectl -n sc4snmp get pods`. This will output all pods:
```
NAME                                                          READY   STATUS    RESTARTS   AGE
snmp-splunk-connect-for-snmp-worker-trap-99f49c557-j9jwx      1/1     Running   0          29m
snmp-splunk-connect-for-snmp-trap-56f75f9754-kmlgb            1/1     Running   0          29m
snmp-splunk-connect-for-snmp-scheduler-7bb8c79855-rgjkj       1/1     Running   0          29m
snmp-mibserver-784bd599fd-6xzfj                               1/1     Running   0          29m
snmp-splunk-connect-for-snmp-worker-poller-78b46d668f-59mv4   1/1     Running   0          29m
snmp-splunk-connect-for-snmp-worker-sender-6f8496bfbf-cvt9l   1/1     Running   0          29m
snmp-mongodb-7579dc7867-mlnst                                 2/2     Running   0          29m
snmp-redis-master-0                                           1/1     Running   0          29m
```

Now select the desired pod and run `microk8s kubectl -n sc4snmp logs pod/<pod-name>` command. Example command to retrieve
logs from `splunk-connect-for-snmp-worker-poller`:
```
microk8s kubectl -n sc4snmp logs pod/snmp-splunk-connect-for-snmp-worker-poller-78b46d668f-59mv4
```

