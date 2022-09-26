# Worker Configuration
The `worker` is a kubernetes pod which is responsible for the actual execution of polling, processing trap messages, and sending 
data to Splunk.

### Worker types

SC4SNMP has two base functionalities: monitoring traps and polling. These operations are handled by 3 types of workers:

1. The `trap` worker consumes all the trap related tasks produced by the trap pod. 

2. The `poller` worker consumes all the tasks related to polling.

3. The `sender` worker handles sending data to Splunk. You need to always have at least one sender pod running.

### Worker configuration file

Worker configuration is kept in the `values.yaml` file in the `worker` section. `worker` has 3 subsections: `poller`, `sender`, or `trap`, that refer to the workers' types.
`values.yaml` is used during the installation process for configuring Kubernetes values.
The `worker` default configuration is:

```yaml
worker:
  # There are 3 types of workers 
  trap:
    # replicaCount: number of trap-worker pods which consumes trap tasks
    replicaCount: 2
    #autoscaling: use it instead of replicaCount in order to make pods scalable by itself
    #autoscaling:
    #  enabled: true
    #  minReplicas: 2
    #  maxReplicas: 10
    #  targetCPUUtilizationPercentage: 80
  poller:
    # replicaCount: number of poller-worker pods which consumes polling tasks
    replicaCount: 2
    #autoscaling: use it instead of replicaCount in order to make pods scalable by itself
    #autoscaling:
    #  enabled: true
    #  minReplicas: 2
    #  maxReplicas: 10
    #  targetCPUUtilizationPercentage: 80
  sender:
    # replicaCount: number of sender-worker pods which consumes sending tasks
    replicaCount: 1
    # autoscaling: use it instead of replicaCount in order to make pods scalable by itself
    #autoscaling:
    #  enabled: true
    #  minReplicas: 2
    #  maxReplicas: 10
    #  targetCPUUtilizationPercentage: 80
  # udpConnectionTimeout: timeout in seconds for SNMP operations
  #udpConnectionTimeout: 5
  logLevel: "INFO"
```

All parameters are described in the [Worker parameters](#worker-parameters) section.


### Worker scaling

You can adjust worker pods in two ways: set fixed value in `replicaCount`,
or enable `autoscaling`, which scales pods automatically. 

#### Real life scenario: I use SC4SNMP for only trap monitoring, I want to use my resources effectively.

If you don't use polling at all, set `worker.poller.replicaCount` to `0`.
If you'll want to use polling in the future, you need to increase `replicaCount`. To monitor traps, adjust `worker.trap.replicaCount` depending on your needs and `worker.sender.replicaCount` to send traps to Splunk. Usually you need much less sender pods than trap ones.

This is the example of `values.yaml` without using autoscaling:

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

This is the example of `values.yaml` with autoscaling:

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

In the example above both trap and sender pods are autoscaled. During an upgrade process, the number of pods is created through
`minReplicas`, and then new ones are created only if the CPU threshold
exceeds the `targetCPUUtilizationPercentage`, which by default is 80%. This solution helps you to keep 
resources usage adjusted to what you actually need. 

After helm upgrade process, you will see `horizontalpodautoscaler` in `microk8s kubectl get all -n sc4snmp`:

```yaml
NAME                                                                             REFERENCE                                               TARGETS   MINPODS   MAXPODS   REPLICAS   AGE
horizontalpodautoscaler.autoscaling/snmp-mibserver                               Deployment/snmp-mibserver                               1%/80%    1         3         1          97m
horizontalpodautoscaler.autoscaling/snmp-splunk-connect-for-snmp-worker-sender   Deployment/snmp-splunk-connect-for-snmp-worker-sender   1%/80%    2         5         2          28m
horizontalpodautoscaler.autoscaling/snmp-splunk-connect-for-snmp-worker-trap     Deployment/snmp-splunk-connect-for-snmp-worker-trap     1%/80%    4         10        4          28m
```

If you see `<unknown>/80%` in `TARGETS` section instead of the CPU percentage, you probably don't have the `metrics-server` add-on enabled.
Enable it using `microk8s enable metrics-server`.


#### Real life scenario: I have a significant delay in polling

Sometimes when polling is configured to be run frequently and on many devices, workers get overloaded 
and there is a delay in delivering data to Splunk. To avoid such situations, we can scale poller and sender pods.
Because of the walk cycles (walk is a costly operation ran once in a while), poller workers require more resources 
for a short time. For this reason, enabling autoscaling is recommended. 

This is the example of `values.yaml` with autoscaling:

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

Remember, that the system won't scale itself infinitely, there is a finite amount of resources that you can allocate.
By default, every worker has configured the following resources:

```yaml
    resources:
      limits:
        cpu: 500m
      requests:
        cpu: 250m
```


#### I have autoscaling enabled and experience problems with Mongo and Redis pod

If MongoDB and Redis pods are crushing, and some of the pods are in infinite `Pending` state, that means 
you're over your resources and SC4SNMP cannot scale more. You should decrease the number of `maxReplicas` in 
workers, so that it's not going beyond the available CPU.

#### I don't know how to set autoscaling parameters and how many replicas I need

The best way to see if pods are overloaded is to run:

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

Here you can see how much CPU and Memory is being used by the pods. If the CPU is close to 500m (which is the limit for one pod by default),
you should enable autoscaling/increase maxReplicas or increase replicaCount with autoscaling off.


Here you can read about Horizontal Autoscaling and how to adjust maximum replica value to the resources you have: [Horizontal Autoscaling.](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)


### Worker parameters

| variable | description | default |
| --- | --- | --- |
| worker.taskTimeout | task timeout in seconds (usually necessary when walk process takes a long time) | 2400 |
| worker.walkRetryMaxInterval | maximum time interval between walk attempts | 600 |
| worker.poller.replicaCount | number of poller worker replicas | 2 |
| worker.poller.autoscaling.enabled | enabling autoscaling for poller worker pods | false |
| worker.poller.autoscaling.minReplicas | minimum number of running poller worker pods when autoscaling is enabled | 2 |
| worker.poller.autoscaling.maxReplicas | maximum number of running poller worker pods when autoscaling is enabled | 40 |
| worker.poller.autoscaling.targetCPUUtilizationPercentage | CPU % threshold that must be exceeded on poller worker pods to spawn another replica  | 80 |
| worker.poller.resources.limits | the resources limits for poller worker container | {} |
| worker.poller.resources.requests | the requested resources for poller worker container | {} |
| worker.trap.replicaCount | number of trap worker replicas | 2 |
| worker.trap.autoscaling.enabled | enabling autoscaling for trap worker pods | false |
| worker.trap.autoscaling.minReplicas | minimum number of running trap worker pods when autoscaling is enabled | 2 |
| worker.trap.autoscaling.maxReplicas | maximum number of running trap worker pods when autoscaling is enabled | 40 |
| worker.trap.autoscaling.targetCPUUtilizationPercentage | CPU % threshold that must be exceeded on trap worker pods to spawn another replica  | 80 |
| worker.trap.resources.limits | the resources limits for poller worker container | {} |
| worker.trap.resources.requests | the requested resources for poller worker container | {} |
| worker.sender.replicaCount | number of sender worker replicas | 2 |
| worker.sender.autoscaling.enabled | enabling autoscaling for sender worker pods | false |
| worker.sender.autoscaling.minReplicas | minimum number of running sender worker pods when autoscaling is enabled | 2 |
| worker.sender.autoscaling.maxReplicas | maximum number of running sender worker pods when autoscaling is enabled | 40 |
| worker.sender.autoscaling.targetCPUUtilizationPercentage | CPU % threshold that must be exceeded on sender worker pods to spawn another replica  | 80 |
| worker.sender.resources.limits | the resources limits for poller worker container | {} |
| worker.sender.resources.requests | the requested resources for poller worker container | {} |
