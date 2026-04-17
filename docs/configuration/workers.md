# Worker configuration

The worker is responsible for the actual execution of polling, processing trap messages, and sending data to Splunk.

## Worker types

SC4SNMP has three types of workers:

1. The `poller` worker consumes all the tasks related to polling.
2. The `trap` worker consumes all the trap related tasks produced by the trap service.
3. The `sender` worker handles sending data to Splunk. You need to always have at least one sender running.

## Configuration

/// tab | microk8s
Worker configuration is kept in the `worker` section of `values.yaml`:

```yaml
worker:
  poller:
    replicaCount: 2
    concurrency: 4
    prefetch: 1
    autoscaling:
      enabled: false
      minReplicas: 2
      maxReplicas: 10
      targetCPUUtilizationPercentage: 80

    resources:
      limits:
        cpu: 500m
      requests:
        cpu: 250m

  trap:
    replicaCount: 2
    resolveAddress:
      enabled: false
      cacheSize: 500 
      cacheTTL: 1800 
    concurrency: 4
    prefetch: 30
    autoscaling:
      enabled: false
      minReplicas: 2
      maxReplicas: 10
      targetCPUUtilizationPercentage: 80
    resources:
      limits:
        cpu: 500m
      requests:
        cpu: 250m
  sender:
    replicaCount: 1
    concurrency: 4
    prefetch: 30
    autoscaling:
      enabled: false
      minReplicas: 2
      maxReplicas: 10
      targetCPUUtilizationPercentage: 80
    resources:
      limits:
        cpu: 500m
      requests:
        cpu: 250m
  livenessProbe:
    enabled: false
    exec:
      command:
        - sh
        - -c
        - test $(($(date +%s) - $(stat -c %Y /tmp/worker_heartbeat))) -lt 10
    initialDelaySeconds: 80
    periodSeconds: 10
  readinessProbe:
    enabled: false
    exec:
      command:
        - sh
        - -c
        - test -e /tmp/worker_ready
    initialDelaySeconds: 30
    periodSeconds: 5
  taskTimeout: 2400
  walkRetryMaxInterval: 180
  walkMaxRetries: 5
  ignoreNotIncreasingOid: []
  logLevel: "INFO"
  disableMongoDebugLogging: true
  podAntiAffinity: soft
  udpConnectionTimeout: 3
  ignoreEmptyVarbinds: false
```

To apply changes, run the upgrade command:

```shell
microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
```

### Worker parameters

| Variable                                                 | Description                                                                                                                     | Default           |
|----------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------|-------------------|
| worker.poller.replicaCount                               | Number of poller worker replicas                                                                                                | 2                 |
| worker.poller.concurrency                                | Minimum number of threads in a poller worker pod                                                                                | 4                 |
| worker.poller.prefetch                                   | Number of tasks consumed from the queue at once                                                                                 | 1                 |
| worker.poller.autoscaling.enabled                        | Enabling autoscaling for poller worker pods                                                                                     | false             |
| worker.poller.autoscaling.minReplicas                    | Minimum number of running poller worker pods when autoscaling is enabled                                                        | 2                 |
| worker.poller.autoscaling.maxReplicas                    | Maximum number of running poller worker pods when autoscaling is enabled                                                        | 10                |
| worker.poller.autoscaling.targetCPUUtilizationPercentage | CPU % threshold that must be exceeded on poller worker pods to spawn another replica                                            | 80                |
| worker.poller.resources.limits                           | The resources limits for poller worker container                                                                                | cpu: 500m         |
| worker.poller.resources.requests                         | The requested resources for poller worker container                                                                             | cpu: 250m         |
| worker.trap.replicaCount                                 | Number of trap worker replicas                                                                                                  | 2                 |
| worker.trap.concurrency                                  | Minimum number of threads in a trap worker pod                                                                                  | 4                 |
| worker.trap.prefetch                                     | Number of tasks consumed from the queue at once                                                                                 | 30                |
| worker.trap.resolveAddress.enabled                       | Enable reverse dns lookup of the IP address of the processed trap                                                               | false             |
| worker.trap.resolveAddress.cacheSize                     | Maximum number of reverse dns lookup result records stored in cache                                                             | 500               |
| worker.trap.resolveAddress.cacheTTL                      | Time to live of the cached reverse dns lookup record in seconds                                                                 | 1800              |
| worker.trap.autoscaling.enabled                          | Enabling autoscaling for trap worker pods                                                                                       | false             |
| worker.trap.autoscaling.minReplicas                      | Minimum number of running trap worker pods when autoscaling is enabled                                                          | 2                 |
| worker.trap.autoscaling.maxReplicas                      | Maximum number of running trap worker pods when autoscaling is enabled                                                          | 10                |
| worker.trap.autoscaling.targetCPUUtilizationPercentage   | CPU % threshold that must be exceeded on trap worker pods to spawn another replica                                              | 80                |
| worker.trap.resources.limits                             | The resource limits for trap worker pod                                                                                         | cpu: 500m         |
| worker.trap.resources.requests                           | The requested resources for trap worker pod                                                                                     | cpu: 250m         |
| worker.sender.replicaCount                               | The number of sender worker replicas                                                                                            | 1                 |
| worker.sender.concurrency                                | Minimum number of threads in a sender worker pod                                                                                | 4                 |
| worker.sender.prefetch                                   | Number of tasks consumed from the queue at once                                                                                 | 30                |
| worker.sender.autoscaling.enabled                        | Enabling autoscaling for sender worker pods                                                                                     | false             |
| worker.sender.autoscaling.minReplicas                    | Minimum number of running sender worker pods when autoscaling is enabled                                                        | 2                 |
| worker.sender.autoscaling.maxReplicas                    | Maximum number of running sender worker pods when autoscaling is enabled                                                        | 10                |
| worker.sender.autoscaling.targetCPUUtilizationPercentage | CPU % threshold that must be exceeded on sender worker pods to spawn another replica                                            | 80                |
| worker.sender.resources.limits                           | The resource limits for sender worker pod                                                                                       | cpu: 500m         |
| worker.sender.resources.requests                         | The requested resources for sender worker pod                                                                                   | cpu: 250m         |
| worker.livenessProbe.enabled                             | Whether the liveness probe is enabled                                                                                           | false             |
| worker.livenessProbe.exec.command                        | The exec command for the liveness probe to run in the container                                                                 | Check values.yaml |
| worker.livenessProbe.initialDelaySeconds                 | Number of seconds after the container has started before liveness probe is initiated                                            | 80                |
| worker.livenessProbe.periodSeconds                       | Frequency of performing the probe in seconds                                                                                    | 10                |
| worker.readinessProbe.enabled                            | Whether the readiness probe should be turned on or not                                                                          | false             |
| worker.readinessProbe.exec.command                       | The exec command for the readiness probe to run in the container                                                                | Check values.yaml |
| worker.readinessProbe.initialDelaySeconds                | Number of seconds after the container has started before readiness probe is initiated                                           | 30                |
| worker.readinessProbe.periodSeconds                      | Frequency of performing the probe in seconds                                                                                    | 5                 |
| worker.taskTimeout                                       | Task timeout in seconds when process takes a long time                                                                          | 2400              |
| worker.walkRetryMaxInterval                              | Maximum time interval between walk attempts                                                                                     | 180               |
| worker.walkMaxRetries                                    | Maximum number of walk retries                                                                                                  | 5                 |
| worker.ignoreNotIncreasingOid                            | Ignoring `occurred: OID not increasing` issues for hosts specified in the array                                                 | []                |
| worker.logLevel                                          | Logging level, possible options: DEBUG, INFO, WARNING, ERROR, CRITICAL, or FATAL                                                | INFO              |
| worker.disableMongoDebugLogging                          | Disable extensive MongoDB and pymongo debug logging on SC4SNMP workers                                                          | true              |
| worker.udpConnectionTimeout                              | Timeout for SNMP operations in seconds                                                                                          | 3                 |
| worker.ignoreEmptyVarbinds                               | Ignores "Empty SNMP response message" in responses                                                                              | false             |
| worker.podAntiAffinity                                   | [Kubernetes documentation](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/#affinity-and-anti-affinity) | soft              |

///

/// tab | docker compose
Worker configuration is set via environment variables in `.env`. The key variables for each worker type are:

```
# Workers configuration
WALK_RETRY_MAX_INTERVAL=180
WALK_MAX_RETRIES=5
METRICS_INDEXING_ENABLED=false
POLL_BASE_PROFILES=true
IGNORE_NOT_INCREASING_OIDS=
WORKER_LOG_LEVEL=INFO
WORKER_DISABLE_MONGO_DEBUG_LOGGING=true
UDP_CONNECTION_TIMEOUT=3
MAX_OID_TO_PROCESS=70
MAX_REPETITIONS=10

# Worker Poller
WORKER_POLLER_CONCURRENCY=4
PREFETCH_POLLER_COUNT=1
WORKER_POLLER_REPLICAS=2
WORKER_POLLER_CPU_LIMIT=1
WORKER_POLLER_MEMORY_LIMIT=500M
WORKER_POLLER_CPU_RESERVATIONS=0.5
WORKER_POLLER_MEMORY_RESERVATIONS=250M
ENABLE_WORKER_POLLER_SECRETS=false

# Worker Sender
WORKER_SENDER_CONCURRENCY=4
PREFETCH_SENDER_COUNT=30
WORKER_SENDER_REPLICAS=1
WORKER_SENDER_CPU_LIMIT=1
WORKER_SENDER_MEMORY_LIMIT=500M
WORKER_SENDER_CPU_RESERVATIONS=0.5
WORKER_SENDER_MEMORY_RESERVATIONS=250M

# Worker Trap
WORKER_TRAP_CONCURRENCY=4
PREFETCH_TRAP_COUNT=30
RESOLVE_TRAP_ADDRESS=false
MAX_DNS_CACHE_SIZE_TRAPS=500
TTL_DNS_CACHE_TRAPS=1800
WORKER_TRAP_REPLICAS=2
WORKER_TRAP_CPU_LIMIT=1
WORKER_TRAP_MEMORY_LIMIT=500M
WORKER_TRAP_CPU_RESERVATIONS=0.5
WORKER_TRAP_MEMORY_RESERVATIONS=250M
```

To apply changes, recreate the worker containers:

```shell
sudo docker compose up -d
```

### Worker parameters

### General

| Variable                     | Description                                                                                                                                            |
|------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------|
| `WALK_RETRY_MAX_INTERVAL`    | Maximum time interval between walk attempts                                                                                                            |
| `WALK_MAX_RETRIES`           | Maximum number of walk retries                                                                                                                         |
| `METRICS_INDEXING_ENABLED`   | Details can be found in [append oid index part to the metrics](poller-configuration.md#append-oid-index-part-to-the-metrics) |
| `POLL_BASE_PROFILES`         | Enable polling base profiles (with IF-MIB and SNMPv2-MIB)                                                                                              |
| `IGNORE_NOT_INCREASING_OIDS` | Ignoring `occurred: OID not increasing` issues for hosts specified in the array, ex: IGNORE_NOT_INCREASING_OIDS=127.0.0.1:164,127.0.0.6                |
| `WORKER_LOG_LEVEL`           | Logging level of the workers, possible options: DEBUG, INFO, WARNING, ERROR, CRITICAL, or FATAL                                                        |
| `UDP_CONNECTION_TIMEOUT`     | Timeout in seconds for SNMP operations                                                                                                                 |
| `MAX_OID_TO_PROCESS`         | Sometimes SNMP Agent cannot accept more than X OIDs per once, so if the error "TooBig" is visible in logs, decrease the number of MAX_OID_TO_PROCESS   |
| `MAX_REPETITIONS`            | The amount of requested next oids in response for each of varbinds in one request sent                                                                 |

### Worker Poller

| Variable                            | Description                                                                |
|-------------------------------------|----------------------------------------------------------------------------|
| `WORKER_POLLER_CONCURRENCY`         | Minimum number of threads in the poller container                          |
| `PREFETCH_POLLER_COUNT`             | How many tasks are consumed from the queue at once in the poller container |
| `WORKER_POLLER_REPLICAS`            | Number of docker replicas of worker poller container                       |
| `WORKER_POLLER_CPU_LIMIT`           | Limit of cpu that worker poller container can use                          |
| `WORKER_POLLER_MEMORY_LIMIT`        | Limit of memory that worker poller container can use                       |
| `WORKER_POLLER_CPU_RESERVATIONS`    | Dedicated cpu resources for worker poller container                        |
| `WORKER_POLLER_MEMORY_RESERVATIONS` | Dedicated memory resources for worker poller container                     |
| `ENABLE_WORKER_POLLER_SECRETS`      | Enable usage of secrets for poller                                         |

### Worker Sender

| Variable                            | Description                                                                |
|-------------------------------------|----------------------------------------------------------------------------|
| `WORKER_SENDER_CONCURRENCY`         | Minimum number of threads in the sender container                          |
| `PREFETCH_SENDER_COUNT`             | How many tasks are consumed from the queue at once in the sender container |
| `WORKER_SENDER_REPLICAS`            | Number of docker replicas of worker sender container                       |
| `WORKER_SENDER_CPU_LIMIT`           | Limit of cpu that worker sender container can use                          |
| `WORKER_SENDER_MEMORY_LIMIT`        | Limit of memory that worker sender container can use                       |
| `WORKER_SENDER_CPU_RESERVATIONS`    | Dedicated cpu resources for worker sender container                        |
| `WORKER_SENDER_MEMORY_RESERVATIONS` | Dedicated memory resources for worker sender container                     |

### Worker Trap

| Variable                          | Description                                                                                      |
|-----------------------------------|--------------------------------------------------------------------------------------------------|
| `WORKER_TRAP_CONCURRENCY`         | Minimum number of threads in the trap container                                                  |
| `PREFETCH_TRAP_COUNT`             | How many tasks are consumed from the queue at once in the trap container                         |
| `RESOLVE_TRAP_ADDRESS`            | Use reverse dns lookup for trap IP address and send the hostname to Splunk                       |
| `MAX_DNS_CACHE_SIZE_TRAPS`        | If RESOLVE_TRAP_ADDRESS is set to true, this is the maximum number of records in cache           |
| `TTL_DNS_CACHE_TRAPS`             | If RESOLVE_TRAP_ADDRESS is set to true, this is the time to live of the cached record in seconds |
| `WORKER_TRAP_REPLICAS`            | Number of docker replicas of worker trap container                                               |
| `WORKER_TRAP_CPU_LIMIT`           | Limit of cpu that worker trap container can use                                                  |
| `WORKER_TRAP_MEMORY_LIMIT`        | Limit of memory that worker trap container can use                                               |
| `WORKER_TRAP_CPU_RESERVATIONS`    | Dedicated cpu resources for worker trap container                                                |
| `WORKER_TRAP_MEMORY_RESERVATIONS` | Dedicated memory resources for worker trap container                                             |
///

## Worker scaling

/// tab | microk8s
You can adjust worker pods in two ways: set a fixed value in `replicaCount`, or enable `autoscaling`, which scales pods automatically.

### Real life scenario: I use SC4SNMP for only trap monitoring

If you do not use polling at all, set `worker.poller.replicaCount` to `0`.
To monitor traps, adjust `worker.trap.replicaCount` depending on your needs and `worker.sender.replicaCount` to send traps to Splunk. Usually, you need significantly fewer sender pods than trap pods.

```yaml
worker:
  trap:
    replicaCount: 4
  sender:
    replicaCount: 1
  poller:
    replicaCount: 0
```

With autoscaling:

```yaml
worker:
  trap:
    autoscaling:
      enabled: true
      minReplicas: 4
      maxReplicas: 10
      targetCPUUtilizationPercentage: 80
  sender:
    autoscaling:
      enabled: true
      minReplicas: 2
      maxReplicas: 5
      targetCPUUtilizationPercentage: 80
  poller:
    replicaCount: 0
```

In the above example, both trap and sender pods are autoscaled. During an upgrade process, the number of pods is created through `minReplicas`, and then new ones are created only if the CPU threshold exceeds the `targetCPUUtilizationPercentage`, which by default is 80%. This solution helps you to keep resources usage adjusted to what you actually need.

After the helm upgrade process, you will see `horizontalpodautoscaler` in `microk8s kubectl get all -n sc4snmp`:

```bash
NAME                                                                             REFERENCE                                               TARGETS   MINPODS   MAXPODS   REPLICAS   AGE
horizontalpodautoscaler.autoscaling/snmp-mibserver                               Deployment/snmp-mibserver                               1%/80%    1         3         1          97m
horizontalpodautoscaler.autoscaling/snmp-splunk-connect-for-snmp-worker-sender   Deployment/snmp-splunk-connect-for-snmp-worker-sender   1%/80%    2         5         2          28m
horizontalpodautoscaler.autoscaling/snmp-splunk-connect-for-snmp-worker-trap     Deployment/snmp-splunk-connect-for-snmp-worker-trap     1%/80%    4         10        4          28m
```

If you see `<unknown>/80%` in the `TARGETS` section instead of the CPU percentage, you probably do not have the `metrics-server` add-on enabled.
Enable it using `microk8s enable metrics-server`.


### Real life scenario: I have a significant delay in polling

Sometimes when polling is configured to be run frequently and on many devices, workers get overloaded and there is a delay in delivering data to Splunk. To avoid these situations, scale poller and sender pods. Because of the walk cycles, (walk is a costly operation that is only run once in a while), poller workers require more resources for a short time. For this reason, enabling autoscaling is recommended.

See the following example of values.yaml with autoscaling:

```yaml
worker:
  trap:
    autoscaling:
      enabled: true
      minReplicas: 4
      maxReplicas: 10
      targetCPUUtilizationPercentage: 80
  sender:
    autoscaling:
      enabled: true
      minReplicas: 2
      maxReplicas: 5
      targetCPUUtilizationPercentage: 80
  poller:
    autoscaling:
      enabled: true
      minReplicas: 2
      maxReplicas: 20
      targetCPUUtilizationPercentage: 80
```

Remember that the system will not scale itself infinitely. There is a finite amount of resources that you can allocate. 
By default, every worker has configured the following resources:

```yaml
    resources:
      limits:
        cpu: 500m
      requests:
        cpu: 250m
```

### I have autoscaling enabled and experience problems with Mongo and Redis pod

If MongoDB and Redis pods are crushing, and some of the pods are in an infinite `Pending` state, that means 
you have exhausted your resources and SC4SNMP cannot scale more. You should decrease the number of `maxReplicas` in 
workers, so that it is not going beyond the available CPU.

### I do not know how to set autoscaling parameters and how many replicas I need

The best way to see if pods are overloaded is to run the following command:

```yaml
microk8s kubectl top pods -n sc4snmp
```

```yaml
NAME                                                          CPU(cores)   MEMORY(bytes)   
snmp-mibserver-7f879c5b7c-nnlfj                               1m           3Mi             
snmp-mongodb-869cc8586f-q8lkm                                 18m          225Mi           
snmp-redis-master-0                                           10m          2Mi             
snmp-splunk-connect-for-snmp-scheduler-558dccfb54-nb97j       2m           136Mi           
snmp-splunk-connect-for-snmp-trap-5878f89bbf-24wrz            2m           129Mi           
snmp-splunk-connect-for-snmp-trap-5878f89bbf-z9gd5            2m           129Mi           
snmp-splunk-connect-for-snmp-worker-poller-599c7fdbfb-cfqjm   260m         354Mi           
snmp-splunk-connect-for-snmp-worker-poller-599c7fdbfb-ztf7l   312m         553Mi           
snmp-splunk-connect-for-snmp-worker-sender-579f796bbd-vmw88   14m           257Mi           
snmp-splunk-connect-for-snmp-worker-trap-5474db6fc6-46zhf     3m           259Mi           
snmp-splunk-connect-for-snmp-worker-trap-5474db6fc6-mjtpv     4m           259Mi   
```

Here you can see how much CPU and Memory is being used by the pods. If the CPU is close to 500m, which is the limit for one pod by default,
enable autoscaling/increase maxReplicas or increase replicaCount with autoscaling off.


See [Horizontal Autoscaling](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/) and [Scaling with Microk8s](../microk8s/mk8s/k8s-microk8s-scaling.md) for more information.
///

/// tab | docker compose
Worker scaling is controlled via replica and resource variables in `.env`. To disable a worker type, set its replica count to `0`:

```
WORKER_POLLER_REPLICAS=0
WORKER_TRAP_REPLICAS=4
WORKER_SENDER_REPLICAS=1
```

Docker Compose does not support autoscaling. To handle higher load, increase the replica counts and concurrency values manually.
///

## Reverse DNS lookup in trap worker

If you want to see the hostname instead of the IP address of the incoming traps in Splunk:

/// tab | microk8s
```yaml
worker:
  trap:
    resolveAddress:
      enabled: true
      cacheSize: 500
      cacheTTL: 1800
```
///

/// tab | docker compose
Set in `.env`:

```
RESOLVE_TRAP_ADDRESS=true
MAX_DNS_CACHE_SIZE_TRAPS=500
TTL_DNS_CACHE_TRAPS=1800
```
///

Trap worker uses in memory cache to store the results of the reverse dns lookup. If you restart the worker, the cache will be cleared.

