# Worker configuration

The worker is responsible for the actual execution of polling, processing trap messages, and sending data to Splunk.

## Worker types

SC4SNMP has three types of workers:

1. The `poller` worker consumes all the tasks related to polling.
2. The `trap` worker consumes all the trap related tasks produced by the trap pod.
3. The `sender` worker handles sending data to Splunk. You need to always have at least one sender pod running.

## Configuration

/// tab | microk8s
Worker configuration is kept in the `worker` section of `values.yaml`:

```yaml
worker:
  poller:
    replicaCount: 2
    concurrency: 4
    prefetch: 1
  trap:
    replicaCount: 2
    concurrency: 4
    prefetch: 30
  sender:
    replicaCount: 1
    concurrency: 4
    prefetch: 30
  logLevel: "INFO"
  udpConnectionTimeout: 3
  walkRetryMaxInterval: 180
  walkMaxRetries: 5
  ignoreNotIncreasingOid: []
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
| worker.sender.replicaCount                               | The number of sender worker replicas                                                                                            | 1                 |
| worker.sender.concurrency                                | Minimum number of threads in a sender worker pod                                                                                | 4                 |
| worker.sender.prefetch                                   | Number of tasks consumed from the queue at once                                                                                 | 30                |
| worker.sender.autoscaling.enabled                        | Enabling autoscaling for sender worker pods                                                                                     | false             |
| worker.sender.autoscaling.minReplicas                    | Minimum number of running sender worker pods when autoscaling is enabled                                                        | 2                 |
| worker.sender.autoscaling.maxReplicas                    | Maximum number of running sender worker pods when autoscaling is enabled                                                        | 10                |
| worker.sender.autoscaling.targetCPUUtilizationPercentage | CPU % threshold that must be exceeded on sender worker pods to spawn another replica                                            | 80                |
| worker.taskTimeout                                       | Task timeout in seconds when process takes a long time                                                                          | 2400              |
| worker.walkRetryMaxInterval                              | Maximum time interval between walk attempts                                                                                     | 180               |
| worker.walkMaxRetries                                    | Maximum number of walk retries                                                                                                  | 5                 |
| worker.ignoreNotIncreasingOid                            | Ignoring `occurred: OID not increasing` issues for hosts specified in the array                                                 | []                |
| worker.logLevel                                          | Logging level, possible options: DEBUG, INFO, WARNING, ERROR, CRITICAL, or FATAL                                                | INFO              |
| worker.udpConnectionTimeout                              | Timeout for SNMP operations in seconds                                                                                          | 3                 |
| worker.ignoreEmptyVarbinds                               | Ignores "Empty SNMP response message" in responses                                                                              | false             |
///

/// tab | docker compose
Worker configuration is set via environment variables in `.env`.

### General

| Variable                     | Description                                                                                                                                            |
|------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------|
| `WALK_RETRY_MAX_INTERVAL`    | Maximum time interval between walk attempts                                                                                                            |
| `WALK_MAX_RETRIES`           | Maximum number of walk retries                                                                                                                         |
| `METRICS_INDEXING_ENABLED`   | Details can be found in [append oid index part to the metrics](../microk8s/configuration/poller-configuration.md#append-oid-index-part-to-the-metrics) |
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
| `ENABLE_WORKER_POLLER_SECRETS`    | Enable usage of secrets for poller                                                               |
///

## Worker scaling

/// tab | microk8s
You can adjust worker pods in two ways: set a fixed value in `replicaCount`, or enable `autoscaling`, which scales pods automatically.

### Real life scenario: I use SC4SNMP for only trap monitoring

If you do not use polling at all, set `worker.poller.replicaCount` to `0`.
To monitor traps, adjust `worker.trap.replicaCount` depending on your needs and `worker.sender.replicaCount` to send traps to Splunk.

```yaml
worker:
  trap:
    replicaCount: 4
  sender:
    replicaCount: 1
  poller:
    replicaCount: 0
  logLevel: "WARNING"
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
  logLevel: "WARNING"
```

### Real life scenario: I have a significant delay in polling

Enable autoscaling for poller and sender pods. Because of walk cycles, poller workers require more resources for a short time.

```yaml
worker:
  poller:
    autoscaling:
      enabled: true
      minReplicas: 2
      maxReplicas: 20
      targetCPUUtilizationPercentage: 80
  sender:
    autoscaling:
      enabled: true
      minReplicas: 2
      maxReplicas: 5
      targetCPUUtilizationPercentage: 80
  trap:
    autoscaling:
      enabled: true
      minReplicas: 4
      maxReplicas: 10
      targetCPUUtilizationPercentage: 80
  logLevel: "WARNING"
```

To see how much CPU and Memory is being used by the pods:

```shell
microk8s kubectl top pods -n sc4snmp
```

If the CPU is close to 500m (the default limit), enable autoscaling or increase `replicaCount`.

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

### Reverse DNS lookup in trap worker

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

