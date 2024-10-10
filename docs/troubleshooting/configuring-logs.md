## Configuring SC4SNMP loglevel

SC4SNMP log level can be configured in `values.yaml` file. The default value for it is `INFO`, other 
possible levels to set are `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` or `FATAL`. To change 
the log level for a specific component, add the following configuration to `values.yaml`:

```yaml
worker:
    logLevel: "DEBUG"
```

And redeploy SC4SNMP. 

Log level configuration can be set for `worker`, `poller`, `scheduler` and `traps`.

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

### Accessing logs in docker

Refer to [splunk logging](../dockercompose/9-splunk-logging.md) for instructions on how to enable logging in docker and 
sent them to Splunk.

To access logs directly in docker, first run `docker ps`. This will output all containers:

```
CONTAINER ID   IMAGE                                                            COMMAND                  CREATED          STATUS          PORTS                                                                                  NAMES
afcd8f4850cd   ghcr.io/splunk/splunk-connect-for-snmp/container:1.12.0-beta.1   "./entrypoint.sh cel…"   19 seconds ago   Up 17 seconds                                                                                          docker_compose-worker-poller-1
5cea46cee0cb   ghcr.io/splunk/splunk-connect-for-snmp/container:1.12.0-beta.1   "./entrypoint.sh cel…"   19 seconds ago   Up 17 seconds                                                                                          docker_compose-worker-sender-1
1c5154c91191   ghcr.io/splunk/splunk-connect-for-snmp/container:1.12.0-beta.1   "./entrypoint.sh cel…"   19 seconds ago   Up 17 seconds                                                                                          sc4snmp-scheduler
8f6e60903780   ghcr.io/splunk/splunk-connect-for-snmp/container:1.12.0-beta.1   "./entrypoint.sh trap"   19 seconds ago   Up 17 seconds   0.0.0.0:2163->2163/udp, :::2163->2163/udp, 0.0.0.0:162->2162/udp, [::]:162->2162/udp   sc4snmp-traps
f146802a0a8d   ghcr.io/splunk/splunk-connect-for-snmp/container:1.12.0-beta.1   "./entrypoint.sh cel…"   19 seconds ago   Up 16 seconds                                                                                          docker_compose-worker-poller-2
70e0fe076cdf   ghcr.io/splunk/splunk-connect-for-snmp/container:1.12.0-beta.1   "./entrypoint.sh cel…"   19 seconds ago   Up 17 seconds                                                                                          docker_compose-worker-trap-2
090cc957b600   ghcr.io/splunk/splunk-connect-for-snmp/container:1.12.0-beta.1   "./entrypoint.sh cel…"   19 seconds ago   Up 16 seconds                                                                                          docker_compose-worker-trap-1
24aac5c89d80   ghcr.io/pysnmp/mibs/container:latest                             "/bin/sh -c '/app/lo…"   19 seconds ago   Up 18 seconds   8080/tcp                                                                               snmp-mibserver
a5bef5a5a02c   bitnami/mongodb:6.0.9-debian-11-r5                               "/opt/bitnami/script…"   19 seconds ago   Up 18 seconds   27017/tcp                                                                              mongo
76f966236c1b   bitnami/redis:7.2.1-debian-11-r0                                 "/opt/bitnami/script…"   19 seconds ago   Up 18 seconds   6379/tcp                                                                               redis
163d880eaf8c   coredns/coredns:1.11.1                                           "/coredns -conf /Cor…"   19 seconds ago   Up 18 seconds   53/tcp, 53/udp                                                                         coredns
```

Now select the desired container and run `docker logs <container_name/id>` command. 
Example command to retrieve logs from `splunk-connect-for-snmp-worker-poller`:

```
docker logs docker_compose-worker-poller-1
```

