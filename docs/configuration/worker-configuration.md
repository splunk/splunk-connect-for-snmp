# Worker Configuration
The worker is a service witch is responsible for tasks execution like SNMP Walk, GET, or processing trap messages.  

### Worker configuration file

Worker configuration is kept in `values.yaml` file in the section `worker`. `worker` is divided on 3 types of workers: `poller`, `sender` and `trap`.
`values.yaml` is being used during the installation process for configuring Kubernetes values.

### Worker types

SC4SNMP has two base functionalities: monitoring traps and polling. There are 3 types of workers, every type is
responsible for something else.

Trap workers consumes all the trap related tasks produced by the trap pod. 

Poller workers consumes all the tasks related to polling.

Sender workers handle sending data to splunk. You need to always have at least one sender pod running.

### Worker parameters

| variable | description | default |
| --- | --- | --- |
| work.taskTimeout | task timeout in seconds (usually necessary when walk process takes a long time) | 2400 |
| work.poller.replicaCount | number of poller worker replicas | 2 |
| work.poller.autoscaling.enabled | enabling autoscaling for poller worker pods | false |
| work.poller.autoscaling.minReplicas | minimum number of running poller worker pods when autoscaling is enabled | 2 |
| work.poller.autoscaling.maxReplicas | maximum number of running poller worker pods when autoscaling is enabled | 40 |
| work.poller.autoscaling.targetCPUUtilizationPercentage | CPU % threshold that must be exceeded on poller worker pods to spawn another replica  | 80 |
| work.poller.resources.limits | the resources limits for poller worker container | {} |
| work.poller.resources.requests | the requested resources for poller worker container | {} |
| work.trap.replicaCount | number of trap worker replicas | 2 |
| work.trap.autoscaling.enabled | enabling autoscaling for trap worker pods | false |
| work.trap.autoscaling.minReplicas | minimum number of running trap worker pods when autoscaling is enabled | 2 |
| work.trap.autoscaling.maxReplicas | maximum number of running trap worker pods when autoscaling is enabled | 40 |
| work.trap.autoscaling.targetCPUUtilizationPercentage | CPU % threshold that must be exceeded on trap worker pods to spawn another replica  | 80 |
| work.trap.resources.limits | the resources limits for poller worker container | {} |
| work.trap.resources.requests | the requested resources for poller worker container | {} |
| work.sender.replicaCount | number of sender worker replicas | 2 |
| work.sender.autoscaling.enabled | enabling autoscaling for sender worker pods | false |
| work.sender.autoscaling.minReplicas | minimum number of running sender worker pods when autoscaling is enabled | 2 |
| work.sender.autoscaling.maxReplicas | maximum number of running sender worker pods when autoscaling is enabled | 40 |
| work.sender.autoscaling.targetCPUUtilizationPercentage | CPU % threshold that must be exceeded on sender worker pods to spawn another replica  | 80 |
| work.sender.resources.limits | the resources limits for poller worker container | {} |
| work.sender.resources.requests | the requested resources for poller worker container | {} |

### Worker scaling

You can adjust number of worker pods to your needs in two ways: setting fixed value in `replicaCount`
or enabling `autoscaling` which scales pods automatically. 

#### Reallife scenario: I use SC4SNMP for only trap monitoring, I want to use my resources effectively

If you don't use polling at all, would be the best to set `worker.poller.replicaCount` to `0`.
Remember, that if you'll want to use polling in the future you need to increase `replicaCount`,
otherwise it won't work. To monitor traps, adjust `worker.trap.replicaCount` depending on your needs
and `worker.sender.replicaCount` to send traps to splunk. Usually you need much less sender pods than trap ones.

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

In the example above both trap and sender pods are autoscaled. During an upgrade process
`minReplicas` number of pods is created, and then new ones are created only if CPU threshold
exceeds `targetCPUUtilizationPercentage` which by default is 80%. This solution helps you to keep 
resources usage adjusted to what you actually need. 

After helm upgrade process, you will see `horizontalpodautoscaler` in `microk8s kubectl get all -n sc4snmp`:

```yaml
NAME                                                                             REFERENCE                                               TARGETS   MINPODS   MAXPODS   REPLICAS   AGE
horizontalpodautoscaler.autoscaling/snmp-mibserver                               Deployment/snmp-mibserver                               1%/80%    1         3         1          97m
horizontalpodautoscaler.autoscaling/snmp-splunk-connect-for-snmp-worker-sender   Deployment/snmp-splunk-connect-for-snmp-worker-sender   1%/80%    2         5         2          28m
horizontalpodautoscaler.autoscaling/snmp-splunk-connect-for-snmp-worker-trap     Deployment/snmp-splunk-connect-for-snmp-worker-trap     1%/80%    4         10        4          28m
```

If you see `<unknown>/80%` in `TARGETS` section instead of the CPU percentage, you probably don't have `metrics-server` addon enabled.
Enable it using: `microk8s enable metrics-server`.


#### Real life scenario: I have a significant delay in polling

Sometimes when polling is configured to be run frequently and on many devices, workers get overloaded 
and there is a delay in delivering data to splunk. To avoid such situations we can scale poller and sender pods.
Because of the walk cycles (walk is a costly operation ran once for a while), poller workers require more resources 
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
By default, every worker has configured following resources:

```yaml
    resources:
      limits:
        cpu: 500m
      requests:
        cpu: 250m
```

You can read about Horizontal Autoscaling and how to adjust maximum replica value to the resources you have
here: [Horizontal Autoscaling.](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)