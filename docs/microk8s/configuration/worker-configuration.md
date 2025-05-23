# Worker Configuration
The `worker` is a kubernetes pod which is responsible for the actual execution of polling, processing trap messages, and sending 
data to Splunk.

### Worker types

SC4SNMP has two base functionalities: monitoring traps and polling. These operations are handled by 3 types of workers:

1. The `trap` worker consumes all the trap related tasks produced by the trap pod. 

2. The `poller` worker consumes all the tasks related to polling.

3. The `sender` worker handles sending data to Splunk. You need to always have at least one sender pod running.

### Worker configuration file

Worker configuration is kept in the `values.yaml` file in the `worker` section. `worker` has 3 subsections: `poller`, `sender`, and `trap`, that refer to the workers types.
`values.yaml` is used during the installation process for configuring Kubernetes values.
The `worker` default configuration is the following: 

```yaml
worker:
  # workers are responsible for the actual execution of polling, processing trap messages, and sending data to Splunk.
  # More: https://splunk.github.io/splunk-connect-for-snmp/main/microk8s/configuration/worker-configuration/

  # The poller worker consumes all the tasks related to polling
  poller:
    # number of the poller replicas when autoscaling is set to false
    replicaCount: 2
    # minimum number of threads in a pod
    concurrency: 4
    # how many tasks are consumed from the queue at once
    prefetch: 1
    autoscaling:
      # enabling autoscaling for poller worker pods
      enabled: false
      # minimum number of running poller worker pods when autoscaling is enabled
      minReplicas: 2
      # maximum number of running poller worker pods when autoscaling is enabled
      maxReplicas: 10
      # CPU % threshold that must be exceeded on poller worker pods to spawn another replica
      targetCPUUtilizationPercentage: 80

    resources:
      # the resources limits for poller worker container
      limits:
        cpu: 500m
      # the resources requests for poller worker container
      requests:
        cpu: 250m

  # The trap worker consumes all the trap related tasks produced by the trap pod
  trap:
    # number of the trap replicas when autoscaling is set to false
    replicaCount: 2
    # Use reverse dns lookup of trap ip address and send the hostname to splunk
    resolveAddress:
      enabled: false
      cacheSize: 500 # maximum number of records in cache
      cacheTTL: 1800 # time to live of the cached record in seconds
    # minimum number of threads in a pod
    concurrency: 4
    # how many tasks are consumed from the queue at once
    prefetch: 30
    autoscaling:
      # enabling autoscaling for trap worker pods
      enabled: false
      # minimum number of running trap worker pods when autoscaling is enabled
      minReplicas: 2
      # maximum number of running trap worker pods when autoscaling is enabled
      maxReplicas: 10
      # CPU % threshold that must be exceeded on traps worker pods to spawn another replica
      targetCPUUtilizationPercentage: 80
    resources:
      # the resources limits for trap worker container
      limits:
        cpu: 500m
      requests:
        # the resources requests for trap worker container
        cpu: 250m
  # The sender worker handles sending data to Splunk
  sender:
    # number of the sender replicas when autoscaling is set to false
    replicaCount: 1
    # minimum number of threads in a pod
    concurrency: 4
    # how many tasks are consumed from the queue at once
    prefetch: 30
    autoscaling:
      # enabling autoscaling for sender worker pods
      enabled: false
      # minimum number of running sender worker pods when autoscaling is enabled
      minReplicas: 2
      # maximum number of running sender worker pods when autoscaling is enabled
      maxReplicas: 10
      # CPU % threshold that must be exceeded on sender worker pods to spawn another replica
      targetCPUUtilizationPercentage: 80
    resources:
      # the resources limits for sender worker container
      limits:
        cpu: 500m
        # the resources requests for sender worker container
      requests:
        cpu: 250m
  # Liveness probes are used in Kubernetes to know when a pod is alive or dead.
  # A pod can be in a dead state for a number of reasons;
  # the application could be crashed, some error in the application etc.
  livenessProbe:
    # whether it should be turned on or not
    enabled: false
    # The exec command for the liveness probe to run in the container.
    exec:
      command:
        - sh
        - -c
        - test $(($(date +%s) - $(stat -c %Y /tmp/worker_heartbeat))) -lt 10
    # Number of seconds after the container has started before liveness probes are initiated.
    initialDelaySeconds: 80
    # How often (in seconds) to perform the probe.
    periodSeconds: 10

  # Readiness probes are used to know when a pod is ready to serve traffic.
  # Until a pod is ready, it won't receive traffic from Kubernetes services.
  readinessProbe:
    # whether it should be turned on or not
    enabled: false
    # The exec command for the readiness probe to run in the container.
    exec:
      command:
        - sh
        - -c
        - test -e /tmp/worker_ready
    # Number of seconds after the container has started before readiness probes are initiated.
    initialDelaySeconds: 30
    # How often (in seconds) to perform the probe.
    periodSeconds: 5


  # task timeout in seconds (usually necessary when walk process takes a long time)
  taskTimeout: 2400
  # maximum time interval between walk attempts
  walkRetryMaxInterval: 180
  # maximum number of walk retries
  walkMaxRetries: 5
  # ignoring `occurred: OID not increasing` issues for hosts specified in the array, ex:
  #   ignoreNotIncreasingOid:
  #    - "127.0.0.1:164"
  #    - "127.0.0.6"
  ignoreNotIncreasingOid: []
  # logging level, possible options: DEBUG, INFO, WARNING, ERROR, CRITICAL, or FATAL
  logLevel: "INFO"
  podAntiAffinity: soft
  # udpConnectionTimeout timeout in seconds for SNMP operations
  udpConnectionTimeout: 3

  # in case of seeing "Empty SNMP response message" this variable can be set to true
  ignoreEmptyVarbinds: false
```

All parameters are described in the [Worker parameters](#worker-parameters) section.


### Worker scaling

You can adjust worker pods in two ways: set fixed value in `replicaCount`,
or enable `autoscaling`, which scales pods automatically. 

#### Real life scenario: I use SC4SNMP for only trap monitoring, and I want to use my resources effectively.

If you do not use polling at all, set `worker.poller.replicaCount` to `0`.
If you want to use polling in the future, you need to increase `replicaCount`. 
To monitor traps, adjust `worker.trap.replicaCount` depending on your needs and `worker.sender.replicaCount` to send traps to Splunk.
Usually, you need significantly fewer sender pods than trap pods.

The following is an example of `values.yaml` without using autoscaling:

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

The following is an example of `values.yaml` with autoscaling:

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

In the previous example, both trap and sender pods are autoscaled. During an upgrade process, the number of pods is created through
`minReplicas`, and then new ones are created only if the CPU threshold
exceeds the `targetCPUUtilizationPercentage`, which by default is 80%. This solution helps you to keep 
resources usage adjusted to what you actually need. 

After the helm upgrade process, you will see `horizontalpodautoscaler` in `microk8s kubectl get all -n sc4snmp`:

```yaml
NAME                                                                             REFERENCE                                               TARGETS   MINPODS   MAXPODS   REPLICAS   AGE
horizontalpodautoscaler.autoscaling/snmp-mibserver                               Deployment/snmp-mibserver                               1%/80%    1         3         1          97m
horizontalpodautoscaler.autoscaling/snmp-splunk-connect-for-snmp-worker-sender   Deployment/snmp-splunk-connect-for-snmp-worker-sender   1%/80%    2         5         2          28m
horizontalpodautoscaler.autoscaling/snmp-splunk-connect-for-snmp-worker-trap     Deployment/snmp-splunk-connect-for-snmp-worker-trap     1%/80%    4         10        4          28m
```

If you see `<unknown>/80%` in the `TARGETS` section instead of the CPU percentage, you probably do not have the `metrics-server` add-on enabled.
Enable it using `microk8s enable metrics-server`.


#### Real life scenario: I have a significant delay in polling

Sometimes when polling is configured to be run frequently and on many devices, workers get overloaded 
and there is a delay in delivering data to Splunk. To avoid these situations, scale poller and sender pods.
Because of the walk cycles, (walk is a costly operation that is only run once in a while), poller workers require more resources 
for a short time. For this reason, enabling autoscaling is recommended. 

See the following example of `values.yaml` with autoscaling:

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
  logLevel: "WARNING"
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


#### I have autoscaling enabled and experience problems with Mongo and Redis pod

If MongoDB and Redis pods are crushing, and some of the pods are in an infinite `Pending` state, that means 
you have exhausted your resources and SC4SNMP cannot scale more. You should decrease the number of `maxReplicas` in 
workers, so that it is not going beyond the available CPU.

#### I do not know how to set autoscaling parameters and how many replicas I need

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


See [Horizontal Autoscaling](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/) to adjust the maximum replica value to the resources you have.

See [Scaling with Microk8s](../mk8s/k8s-microk8s-scaling.md) for more information.

### Reverse DNS lookup in trap worker

If you want to see the hostname instead of the IP address of the incoming traps in Splunk, you can enable reverse dns lookup
for the incoming traps using the following configuration:

```yaml
worker:
  trap:
    resolveAddress:
      enabled: true
      cacheSize: 500 # maximum number of records in cache
      cacheTTL: 1800 # time to live of the cached record in seconds
```

Trap worker uses in memory cache to store the results of the reverse dns lookup. If you restart the worker, the cache will be cleared.

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
| worker.trap.resources.limits                             | The resource limit for the poller worker container                                                                              | cpu: 500m         |
| worker.trap.resources.requests                           | The requested resources for the poller worker container                                                                         | cpu: 250m         |
| worker.sender.replicaCount                               | The number of sender worker replicas                                                                                            | 1                 |
| worker.sender.concurrency                                | Minimum number of threads in a sender worker pod                                                                                | 4                 |
| worker.sender.prefetch                                   | Number of tasks consumed from the queue at once                                                                                 | 30                |
| worker.sender.autoscaling.enabled                        | Enabling autoscaling for sender worker pods                                                                                     | false             |
| worker.sender.autoscaling.minReplicas                    | Minimum number of running sender worker pods when autoscaling is enabled                                                        | 2                 |
| worker.sender.autoscaling.maxReplicas                    | Maximum number of running sender worker pods when autoscaling is enabled                                                        | 10                |
| worker.sender.autoscaling.targetCPUUtilizationPercentage | CPU % threshold that must be exceeded on sender worker pods to spawn another replica                                            | 80                |
| worker.sender.resources.limits                           | The resource limit for the poller worker container                                                                              | cpu: 500m         |
| worker.sender.resources.requests                         | The requested resources for the poller worker container                                                                         | cpu: 250m         |
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
| worker.podAntiAffinity                                   | [Kubernetes documentation](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/#affinity-and-anti-affinity) | soft              |
| worker.udpConnectionTimeout                              | Timeout for SNMP operations in seconds                                                                                          | 3                 |
| worker.ignoreEmptyVarbinds                               | Ignores “Empty SNMP response message” in responses                                                                              | false             |
