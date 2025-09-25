# Configurable values

## Image Section

Detailed documentation about configuring images section can be found in [kubernetes documentation](https://kubernetes.io/docs/concepts/containers/images/).
Below are the most common options:

| Variable     | Description                                                 | Example                                            |
|--------------|-------------------------------------------------------------|----------------------------------------------------|
| `repository` | Defines a registry from which container image is downloaded | `ghcr.io/splunk/splunk-connect-for-snmp/container` |
| `tag`        | Defines different versions of images to pull                | `1.21.1`                                           |
| `pullPolicy` | Defines when kubelet attempts to pull the specified image   | `Always`                                           |

## UI section

Detailed documentation about configuring UI can be found in [Enable GUI](../gui/enable-gui.md).

| Variable              | Description                                                                                          | Default                               |
|-----------------------|------------------------------------------------------------------------------------------------------|---------------------------------------|
| `enable`              | Enabling GUI for user                                                                                | `false`                               |
| `frontEnd`            | Section with configuration for frontEnd image                                                        |                                       |
| `backEnd`             | Section with configuration for backEnd image                                                         |                                       |
| `NodePort`            | Port number for accessing UI                                                                         | `frontEnd - 30001`, `backend - 30002` |
| `image`               | Refer to [Image Section](./#image-section)                                                           |                                       |
| `valuesFileDirectory` | Absolute directory path on the host machine where configuration files from the GUI will be generated |                                       |
| `valuesFileName`      | Full name of the file with configuration, stored inside the `valuesFileDirectory`                    |                                       |
| `keepSectionFiles`    | Decides if additional configuration files should be generated                                        | `true`                                |

## Splunk section

| Variable                   | Description                                                                 | Default                                |
|----------------------------|-----------------------------------------------------------------------------|----------------------------------------|
| `enabled`                  | Enables sending data to Splunk                                              | `true`                                 |
| `protocol`                 | The protocol of the HEC endpoint: `https` or `http`                         | `https`                                |
| `port`                     | The port of the HEC endpoint                                                | `8088`                                 |
| `host`                     | IP address or a domain name of a Splunk instance                            |                                        |
| `path`                     | URN to Splunk collector                                                     | `/services/collector`                  | 
| `token`                    | Splunk HTTP Event Collector token                                           | `00000000-0000-0000-0000-000000000000` |
| `insecureSSL`              | Checks for the certificate of the HEC endpoint when sending data over HTTPS | `false`                                |
| `sourcetypeTraps`          | Source type for trap events                                                 | `sc4snmp:traps`                        |
| `sourcetypePollingEvents`  | Source type for non-metric polling event                                    | `sc4snmp:event`                        |
| `sourcetypePollingMetrics` | Source type for metric polling event                                        | `sc4snmp:metric`                       |
| `eventIndex`               | Name of the event index                                                     | `netops`                               |
| `metricsIndex`             | Name of the metrics index                                                   | `netmetrics`                           |

## Sim section

Detailed documentation about configuring sim can be found in [Splunk Infrastructure Monitoring](sim-configuration.md).

| Variable                                        | Description                                                                                                                     | Default |
|-------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------|---------|
| `enabled`                                       | Enables sending data to Splunk Observability Cloud/ SignalFx                                                                    | `false` |
| `signalfxToken`                                 | Splunk Observability org access token                                                                                           |         |
| `signalfxRealm`                                 | Splunk Observability realm to send telemetry data to                                                                            |         |
| `resources`                                     | CPU and memory limits and requests for pod                                                                                      |         |
| `service.annotations`                           | Annotations to append under sim service                                                                                         |         |
| `secret.create`                                 | Option to configure `signalfxToken` and `signalfxRealm` as kubernetes secrets                                                   | `true`  |
| `secret.name`                                   | Name of existing secret in kubernetes with `signalfxToken` and `signalfxRealm`                                                  |         |
| `replicaCount`                                  | Number of created replicas when autoscaling is disabled                                                                         | `1`     |
| `autoscaling.enabled`                           | Enables autoscaling for pods                                                                                                    | `false` |
| `image`                                         | Refer to [Image Section](./#image-section)                                                                                      |         |
| `autoscaling.minReplicas`                       | Minimum number of running pods when autoscaling is enabled                                                                      |         |
| `autoscaling.maxReplicas`                       | Maximum number of running pods when autoscaling is enabled                                                                      |         |
| `autoscaling.targetCPUUtilizationPercentage`    | CPU % threshold that must be exceeded on pods to spawn another replica                                                          |         |
| `autoscaling.targetMemoryUtilizationPercentage` | Memory % threshold that must be exceeded on pods to spawn another replica                                                       |         |
| `podAntiAffinity`                               | [Kubernetes documentation](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/#affinity-and-anti-affinity) | `soft`  |
| `nodeSelector`                                  | [Kubernetes documentation](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/#nodeselector)               |         |


## Scheduler

Detailed documentation about configuring:

 - scheduler can be found in [Scheduler](scheduler-configuration.md).
 - groups can be found in [Configuring Groups](configuring-groups.md).
 - profiles can be found in [Configuring Profiles](configuring-profiles.md).

| Variable             | Description                                                                                                                     | Default |
|----------------------|---------------------------------------------------------------------------------------------------------------------------------|---------|
| `groups`             | Creates groups of host devices to collect data from                                                                             |         |
| `profiles`           | Definitions of data to poll from devices                                                                                        |         |
| `customTranslations` | Sets custom names for mapping MIB fields                                                                                        |         |
| `resources`          | CPU and memory limits and requests for pod                                                                                      |         |
| `logLevel`           | Log level for a scheduler                                                                                                       | `INFO`  |
| `tasksExpiryTime`    | Tasks expiration time in seconds                                                                                                | `60`    |
| `communities`        | Defines a version of SNMP protocol and SNMP community string                                                                    |         |
| `podAntiAffinity`    | [Kubernetes documentation](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/#affinity-and-anti-affinity) | `soft`  |
| `nodeSelector`       | [Kubernetes documentation](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/#nodeselector)               |         |
| `tolerations`        | [Kubernetes documentation](https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/)                       |         |

## Poller

Detailed documentation about configuring poller can be found in [Poller](poller-configuration.md).

| Variable                             | Description                                                                                                     | Default |
|--------------------------------------|-----------------------------------------------------------------------------------------------------------------|---------|
| `metricsIndexingEnabled`             | Appends OID indexes to metrics                                                                                  | `false` |
| `splunkMetricNameHyphenToUnderscore` | Replaces hyphens with underscores in generated metric names to ensure compatibility with Splunk's metric schema | `false` |
| `pollBaseProfiles`                   | Enables polling base profiles                                                                                   | `true`  |
| `maxOidToProcess`                    | Maximum number of OIDs requested from SNMP Agent at once                                                        | `70`    |
| `ipv6Enabled`                        | Enables polling for IPv6 addresses                                                                              | `false` |
| `enableFullWalk`                     | Enables full walk of OIDs from device                                                                           | `false` |
| `usernameSecrets`                    | List of kubernetes secrets name that will be used for polling                                                   |         |
| `inventory`                          | List of configuration for polling                                                                               |         |
| `logLevel`                           | Log level for a poller pod                                                                                      | `INFO`  |

## Worker

Detailed documentation about configuring worker can be found in [Worker](worker-configuration.md).

| Variable                                       | Description                                                                                                                     | Default                                     | 
|------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------|
| `poller`                                       | Section with configuration for worker poller pods                                                                               |                                             |
| `trap`                                         | Section with configuration for worker trap pods                                                                                 |                                             |
| `sender`                                       | Section with configuration for worker sender pods                                                                               |                                             |
| `x.replicaCount`                               | Number of pod replicas when autoscaling is disabled                                                                             | poller/trap - `2`, sender - `1`             |
| `x.concurrency`                                | Minimum number of threads in a pod                                                                                              | `4`                                         |
| `x.prefetch`                                   | Number of tasks consumed from the queue at once                                                                                 | poller - `1`, traps/sender - `30`           |
| `x.autoscaling.enabled`                        | Enables autoscaling for pod                                                                                                     | poller - `false`                            |
| `x.autoscaling.minReplicas`                    | Minimum number of running pods when autoscaling is enabled                                                                      | poller - `2`                                |
| `x.autoscaling.maxReplicas`                    | Maximum number of running pods when autoscaling is enabled                                                                      | poller - `10`                               |
| `x.autoscaling.targetCPUUtilizationPercentage` | CPU % threshold that must be exceeded on pods to spawn another replica                                                          | poller - `80`                               |
| `x.resources`                                  | CPU and memory limits and requests for pod                                                                                      |                                             |
| `trap.resolveAddress.cacheSize`                | Maximum number of records in cache                                                                                              | `500`                                       |
| `trap.resolveAddress.cacheTTL`                 | Time to live of the cached record in seconds                                                                                    | `1800`                                      |
| `livenessProbe`                                | Liveness probes are used in Kubernetes to know when a pod is alive or dead                                                      |                                             |
| `readinessProbe`                               | Readiness probes are used to know when a pod is ready to serve traffic                                                          |                                             |
| `xProbe.enabled`                               | If livenessProbe or readinessProbe are enabled                                                                                  |                                             |
| `xProbe.exec.command`                          | The exec command for the probe to run in the container                                                                          | Check `values.yaml`                         |
| `xProbe.initialDelaySeconds`                   | Number of seconds after the container has started before probes are initiated                                                   | livenessProbe - `80`, readinessProbe - `30` |
| `xProbe.periodSeconds`                         | Frequency of performing the probe in seconds                                                                                    | livenessProbe - `10`, readinessProbe - `5`  |
| `taskTimeout`                                  | Task timeout in seconds when process takes a long time                                                                          | `2400`                                      |
| `walkRetryMaxInterval`                         | Maximum time interval between walk attempts                                                                                     | `180`                                       |
| `walkMaxRetries`                               | Maximum number of walk retries                                                                                                  | `5`                                         |
| `ignoreNotIncreasingOid`                       | Ignoring `occurred: OID not increasing` issues for hosts specified in the array                                                 |                                             |
| `profilesReloadDelay`                          | Delay of polling profiles after inventory reload                                                                                | `60`                                        |
| `logLevel`                                     | Log level for workers                                                                                                           | `INFO`                                      |
| `udpConnectionTimeout`                         | Timeout for SNMP operations in seconds                                                                                          | `3`                                         |
| `ignoreEmptyVarbinds`                          | Ignores "Empty SNMP response message" in responses                                                                              | `false`                                     |
| `podAntiAffinity`                              | [Kubernetes documentation](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/#affinity-and-anti-affinity) | `soft`                                      |
| `nodeSelector`                                 | [Kubernetes documentation](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/#nodeselector)               |                                             |
| `tolerations`                                  | [Kubernetes documentation](https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/)                       |                                             |

## Inventory

Detailed documentation about configuring inventory can be found in [Poller](../poller-configuration#configure-inventory).

| Variable              | Description                                                                                                       | Default |
|-----------------------|-------------------------------------------------------------------------------------------------------------------|---------|
| `secret.create`       | Enables creation of the kubernetes secret                                                                         | `true`  |
| `secret.name`         | Name of existing secret in kubernetes                                                                             |         |
| `service.annotations` | Annotations to append under inventory service                                                                     |         |
| `resources`           | CPU and memory limits and requests for pod                                                                        |         |
| `nodeSelector`        | [Kubernetes documentation](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/#nodeselector) |         |
| `tolerations`         | [Kubernetes documentation](https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/)         |         |

## Traps

Detailed documentation about configuring traps can be found in [Traps](trap-configuration.md).

| Variable                                        | Description                                                                                                                     | Default          |
|-------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------|------------------|
| `replicaCount`                                  | Number of created replicas when autoscaling disabled                                                                            | `2`              |
| `usernameSecrets`                               | Defines SNMPv3 secrets for trap messages sent by SNMP device                                                                    |                  |
| `securityEngineId`                              | SNMP Engine ID of the TRAP sending application                                                                                  | `80003a8c04`     |
| `aggregateTrapsEvents`                          | Enables collecting traps events as one event inside Splunk                                                                      | `false`          |
| `includeSecurityContextId`                      | Controls whether to add the context_engine_id field to v3 trap events                                                           | `false`          |
| `communities`                                   | Defines a version of SNMP protocol and SNMP community string                                                                    |                  |
| `service.annotations`                           | Annotations to append under traps service                                                                                       |                  |
| `service.usemetallb`                            | Enables using metallb                                                                                                           | `true`           |
| `service.metallbsharingkey`                     | Sets metallb.universe.tf/allow-shared-ip annotation in trap service                                                             | `splunk-connect` |
| `service.type`                                  | [Kubernetes documentation](https://kubernetes.io/docs/concepts/services-networking/service/#publishing-services-service-types)  | `LoadBalancer`   |
| `service.port`                                  | Port of the service to use for IPv4 and IPv6                                                                                    | `162`            |
| `service.nodePort`                              | Port when the `service.type` is `nodePort`                                                                                      | `30000`          |
| `service.externalTrafficPolicy`                 | Controls how Kubernetes routes traffic                                                                                          | `Local`          |
| `loadBalancerIP`                                | Sets loadBalancer IP address in the metallb pool                                                                                | ``               |
| `ipFamilyPolicy`                                | Specifies if the service is dual stack or single stack                                                                          | `SingleStack`    |
| `ipFamilies`                                    | Defines the address families used for chosen `ipFamilyPolicy`                                                                   | `IPv4`           |
| `resources`                                     | CPU and memory limits and requests for pod                                                                                      |                  |
| `autoscaling.enabled`                           | Enables autoscaling for pods                                                                                                    | `false`          |
| `autoscaling.minReplicas`                       | Minimum number of running pods when autoscaling is enabled                                                                      | `1`              |
| `autoscaling.maxReplicas`                       | Maximum number of running pods when autoscaling is enabled                                                                      | `100`            |
| `autoscaling.targetCPUUtilizationPercentage`    | CPU % threshold that must be exceeded on pods to spawn another replica                                                          | `80`             |
| `autoscaling.targetMemoryUtilizationPercentage` | Memory % threshold that must be exceeded on pods to spawn another replica                                                       |                  |
| `logLevel`                                      | Log level for a traps pod                                                                                                       | `INFO`           |
| `podAntiAffinity`                               | [Kubernetes documentation](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/#affinity-and-anti-affinity) | `soft`           |
| `nodeSelector`                                  | [Kubernetes documentation](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/#nodeselector)               |                  |
| `tolerations`                                   | [Kubernetes documentation](https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/)                       |                  |

## serviceAccount

| Variable      | Description                                           | Default |
|---------------|-------------------------------------------------------|---------|
| `create`      | Specifies whether a service account should be created | `true`  |
| `annotations` | Annotations to add to the service account             |         |
| `name`        | The name of the service account to use.               |         |

## MongoDb

Detailed documentation about configuring mongodb can be found in [MongoDB](mongo-configuration.md). It is advised to 
not change those settings.

## Redis

Detailed documentation about configuring redis can be found in [Redis](redis-configuration.md). It is advised to not 
change those settings.

## Others

| Variable            | Description                                                                                                              | Default |
|---------------------|--------------------------------------------------------------------------------------------------------------------------|---------|
| `imagePullSecrets`  | [Kubernetes documentation ](https://kubernetes.io/docs/concepts/containers/images/#specifying-imagepullsecrets-on-a-pod) |         |
| `useDeprecatedAPI`  | Enables older version of Kubernetes to use                                                                               | `false` |
| `commonAnnotations` | Annotations added to all services                                                                                        |         |