# MongoDB Configuration

MongoDB serves as the persistent data store for SC4SNMP, storing device profiles, inventory data, task metadata, and SNMP walk results. It is a critical component for maintaining state and configuration across the application.

!!!note
    Previously, MongoDB in our stack was provided via the Bitnami Helm chart. As Bitnami transitions certain components to a paid model, we have replaced it with our own Kubernetes manifests, implementing the necessary deployment logic in-house.
    This change ensures we maintain full control over configuration, compatibility, and licensing. If you encounter any issues or identify missing configuration options, please open an issue in the project repository so we can address it promptly.

### MongoDB configuration file

MongoDB configuration is maintained in the `mongodb` section of `values.yaml`, which is used during installation to configure Kubernetes resources.
This is the snippet of MongoDB's configuration with all available options, filled with example values:

```yaml
mongodb:
  # Mode selector: "standalone", "replication"
  mode: replication

  # Enable IPv6 support
  ipv6Enabled: false

  # Replica set configuration (used only when mode = "replication")
  replicaCount: 3
  replicaSetName: rs0

  # Authentication
  auth:
    enabled: false
    rootUser: "admin"
    rootPassword: ""                  # Set if auth.enabled: true
    existingSecret: ""                # Or reference existing secret
    rootUserKey: "root-user"
    rootPasswordKey: "root-password"

  # Settings used when enabling authentication on an existing replica set.
  replicationAuthTransition:
    # Maximum duration in seconds. Zero calculates it from replicaCount and replicaInitJob.timeout.
    transitionTimeout: 0

  # Image
  image:
    repository: mongo
    tag: "8.2.2"
    pullPolicy: IfNotPresent

  # Resources
  resources:
    requests:
      memory: "512Mi"
      cpu: "250m"
    limits:
      memory: "1Gi"
      cpu: "500m"

  # Storage
  persistence:
    enabled: true
    size: 10Gi
    storageClassName: ""
    accessMode: ReadWriteOnce

  # Security
  podSecurityContext:
    fsGroup: 999
    fsGroupChangePolicy: "OnRootMismatch"

  containerSecurityContext:
    runAsUser: 999
    runAsGroup: 999
    runAsNonRoot: true
    allowPrivilegeEscalation: false
    capabilities:
      drop:
      - ALL

  # Extra environment variables injected into the mongod container.
  extraEnv:
    - name: GLIBC_TUNABLES
      value: "glibc.pthread.rseq=1"
```

| Key                                        | Type   | Default                                                   | Description                                                      |
|--------------------------------------------|--------|-----------------------------------------------------------|------------------------------------------------------------------|
| mongodb.mode                               | string | standalone                                                | Deployment mode (standalone or replication).                     |
| mongodb.ipv6Enabled                        | bool   | false                                                     | Enable IPv6 support for MongoDB. See [Enable IPv6](../enable-ipv6.md). |
| mongodb.replicaCount                       | int    | 3                                                         | Number of MongoDB pods used in replication mode. Use an odd number to support majority-based PRIMARY elections. |
| mongodb.replicaSetName                     | string | rs0                                                       | Internal replica set identifier (used only in replication mode). |
| mongodb.auth.enabled                       | bool   | true                                                      | Enable MongoDB authentication.                                   |
| mongodb.auth.rootUser                      | string | admin                                                     | Root username for MongoDB.                                       |
| mongodb.auth.rootPassword                  | string | ""                                                        | Root password (avoid committing; prefer secret).                 |
| mongodb.auth.existingSecret                | string | ""                                                        | Name of existing Kubernetes Secret providing credentials.        |
| mongodb.auth.rootUserKey                   | string | root-user                                                 | Key inside existing secret containing the username.              |
| mongodb.auth.rootPasswordKey               | string | root-password                                             | Key inside existing secret containing the password.              |
| mongodb.replicationAuthTransition.transitionTimeout| int    | 0                                                         | Timeout in seconds for changing authentication from disabled to enabled in replication mode. A value of 0 uses an automatically calculated timeout. |
| mongodb.image.repository                   | string | mongo                                                     | Container image repository.                                      |
| mongodb.image.tag                          | string | 8.2.2                                                     | Image tag / MongoDB version.                                     |
| mongodb.image.pullPolicy                   | string | IfNotPresent                                              | Image pull policy.                                               |
| mongodb.resources.requests.cpu             | string | ""                                                        | Guaranteed minimum CPU.                                          |
| mongodb.resources.requests.memory          | string | ""                                                        | Guaranteed minimum memory.                                       |
| mongodb.resources.limits.cpu               | string | ""                                                        | CPU limit.                                                       |
| mongodb.resources.limits.memory            | string | ""                                                        | Memory limit.                                                    |
| mongodb.persistence.enabled                | bool   | true                                                      | Create PersistentVolumeClaim.                                    |
| mongodb.persistence.storageClassName       | string | ""                                                        | StorageClass for the PVC (empty = default).                      |
| mongodb.persistence.accessMode             | string | ReadWriteOnce                                             | PVC access mode.                                                 |
| mongodb.persistence.size                   | string | 10Gi                                                      | Requested persistent volume size.                                |
| mongodb.podSecurityContext.fsGroup         | int    | 999                                                       | FS group owning mounted volumes.                                 |
| mongodb.containerSecurityContext.runAsUser | int    | 999                                                       | UID for the container (non-root hardening).                      |
| mongodb.replicaInitJob.image.repository    | string | alpine/kubectl                                            | Container image for the initialization job.                      |
| mongodb.replicaInitJob.image.tag           | string | 1.36.3                                                    | Image tag / kubectl version.                                     |
| mongodb.replicaInitJob.timeout             | int    | 600                                                       | Maximum time (in seconds) to wait for each pod to become ready.  |
| mongodb.extraEnv                           | list   | `[{name: GLIBC_TUNABLES, value: "glibc.pthread.rseq=1"}]` | Extra environment variables injected into the mongod container. The default `GLIBC_TUNABLES` entry mitigates a MongoDB 8.x SIGSEGV observed on host kernels >= 6.19 (e.g. Ubuntu 26.04 / kernel 6.19+ HWE backports). See [MongoDB 8.x crash on Linux kernel 6.19+](../../troubleshooting/general-issues.md#mongodb-8x-crash-on-linux-kernel-619-exit-139-sigsegv). |

!!!note "Extra environment variables (`mongodb.extraEnv`)"
    `mongodb.extraEnv` is a list of standard Kubernetes env entries appended to the mongod container. It ships with a single default entry that sets `GLIBC_TUNABLES=glibc.pthread.rseq=1`, which restores the upstream glibc default and prevents a tcmalloc SIGSEGV (`exit 139`) that occurs ~30s after `startup complete` on host nodes running Linux kernel 6.19 or later. The setting is a no-op on kernels < 6.19. To override or extend the list, redefine `mongodb.extraEnv` in your `values.yaml`.

### Architecture Modes

#### Standalone Mode (Default)

**Architecture**:

* Single MongoDB pod
* Simple deployment
* Minimal resource overhead

Use cases:

* Single-node environments
* Development and testing
* Non-critical workloads

Characteristics:

* Resources: 1 MongoDB pod
* Complexity: Low
* Recovery time: ~30-60 seconds (Kubernetes reschedules pod on node failure)
* No automatic failover

##### Configuration

```yaml
mongodb:
  architecture: standalone
```

#### Replication Mode

**Architecture**:

* 3 MongoDB pods (1 PRIMARY + 2 SECONDARY)
* Automatic failover using MongoDB replica set
* Data replication across all members

Use cases:

* Production deployments
* Multi-node Kubernetes clusters
* Critical workloads requiring high availability

Characteristics:

* Recovery time: ~10-15 seconds (automatic PRIMARY election)
* Resources: 3 MongoDB pods + 1 init job
* Automatic failover when PRIMARY fails
* Read scaling via SECONDARY members

##### Configuration

```yaml
mongodb:
  mode: replication
  replicaCount: 3
  replicaSetName: rs0
```

!!!note "MongoDB replica key"
    When replication and authentication are enabled, the chart manages the Secret named `<release-name>-mongodb-replicakey` for internal authentication between MongoDB members. It generates a key when the Secret does not exist and reuses the existing value on later upgrades. MongoDB Pods copy this key during startup, so the Secret name is not configurable and the Secret must not be modified or deleted while the authenticated replica set is running. If the Secret is accidentally deleted, existing members may continue working, but an upgrade or Pod restart can introduce a different key and prevent members from authenticating. Restore the exact original Secret before restarting a MongoDB Pod or performing a Helm upgrade.

!!!note
    The replica set is automatically initialized by a Kubernetes Job after all pods are ready. No manual intervention is required.

##### Storage Considerations

For true high availability with pod rescheduling across nodes, you must use network-attached storage that supports dynamic provisioning. Node-local storage (like microk8s-hostpath) prevents failed pods from attaching their volumes on different nodes.

Example using block storage in replication mode:

```yaml
mongodb:
  persistence:
    enabled: true
    storageClassName: openebs-jiva-csi-default
    size: 5Gi
    accessMode: ReadWriteOnce
```

!!!note
    The storageClassName must point to a StorageClass that supports block storage with ReadWriteOnce access mode. Examples: AWS EBS (gp3), GCP Persistent Disk (pd-ssd), Azure Disk, Ceph RBD, Longhorn.

### Resource Requirements

MongoDB memory requirements depend on your working set size, index size, and query patterns.

Quick sizing guidance:

Small datasets (<5GB): 1-2GB memory
Medium datasets (5-50GB): 2-4GB memory
Large datasets (>50GB): 4GB+ memory

Example configuration:

```yaml
mongodb:
  resources:
    requests:
      cpu: 500m
      memory: 2Gi
    limits:
      cpu: 2000m
      memory: 4Gi
```

By default, resource limits are set as shown in the configuration table above. Adjust based on your workload.

### Use authentication for MongoDB

MongoDB authentication is enabled by default and strongly recommended for production deployments.

#### Using Direct Password

Set the password directly in `values.yaml`:

```
mongodb:
  auth:
    enabled: true
    rootUser: "admin"
    rootPassword: "your_secure_password_here"
```

#### Using Existing Kubernetes Secret

To use an existing Kubernetes Secret, first create it:

```yaml
microk8s kubectl create secret generic prod-mongodb-secret -n <namespace> \
  --from-literal=root-user='admin' \
  --from-literal=root-password='your_secure_password_here'
```

Then reference it in `values.yaml`:

```yaml
mongodb:
  auth:
    enabled: true
    existingSecret: "prod-mongodb-secret"
```

The secret keys (`root-user` and `root-password`) are configurable via `rootUserKey` and `rootPasswordKey` if your secret uses different key names:

```yaml
mongodb:
  auth:
    enabled: true
    existingSecret: "prod-mongodb-secret-with-different-keys"
    rootUserKey: "my-username-key"
    rootPasswordKey: "my-password-key"
```

### Rotating the MongoDB password

!!!warning
    The `mongo` container image only applies `MONGO_INITDB_ROOT_USERNAME` / `MONGO_INITDB_ROOT_PASSWORD`
    the **first time** it starts against an empty data directory. On an already-initialized
    deployment (an existing PVC), simply changing `mongodb.auth.rootPassword` or the root-password
    Secret and running `helm upgrade` does **not** change the password stored inside MongoDB. The
    database keeps the old password while application pods pick up the new one from the Secret,
    which breaks authentication for every SC4SNMP component (worker, scheduler, traps, inventory,
    discovery, UI).

To rotate the password without losing data, perform the steps **in this order**:

1. **Re-key the running database**, authenticating with the *current* (old) password:

    ```bash
    micrk8s kubectl exec -it <release>-mongodb-0 -n <namespace> -- mongosh \
      -u admin -p '<OLD_PASSWORD>' --authenticationDatabase admin \
      --eval 'db.getSiblingDB("admin").changeUserPassword("admin","<NEW_PASSWORD>")'
    ```

    !!!note
        In **replication mode**, the password change must be run against the current PRIMARY.
        Right after initialization this is `<release>-mongodb-0`. If unsure, connect to any pod
        and run `db.hello().primary` (or `rs.status()`) to find it. The change then replicates
        to the other members automatically.

2. **Update the credential source Helm/pods will use next**, then apply it:
    - Direct password: set the new value in `mongodb.auth.rootPassword` in `values.yaml`.
    - Existing Secret: update the `root-password` key of that Secret (e.g. via
      `microk8s kubectl create secret generic ... --dry-run=client -o yaml | kubectl apply -f -`
      or `microk8s kubectl patch secret`).

    Then run `helm upgrade` so the chart picks up the change.

3. **Restart the application pods** so they re-read the updated credentials:

    ```bash
    microk8s kubectl rollout restart statefulset,deployment -n <namespace>
    ```

!!!danger
    Do not update the Secret or `values.yaml` before completing step 1. If the Secret is changed
    first, MongoDB and the application pods will disagree on the password and every component
    will fail to authenticate until the database is re-keyed with the old password (see
    [Troubleshooting: MongoDB authentication fails after changing the root password](../../troubleshooting/general-issues.md#mongodb-authentication-fails-after-changing-the-root-password)).

This procedure applies to kubernetes deployments only.

### Enable authentication on an existing replica set

Changing `mongodb.auth.enabled` from `false` to `true` during a Helm upgrade starts an automatic two-phase migration based on MongoDB's [`transitionToAuth` procedure](https://www.mongodb.com/docs/manual/tutorial/enforce-keyfile-access-control-in-existing-replica-set-without-downtime/). The chart creates or verifies the configured administrator and rolls the replica-set members into authenticated operation.

MongoDB elects a PRIMARY through a majority of voting members, so use an odd `mongodb.replicaCount`. The transition requires at least three healthy members and a healthy SECONDARY that can become PRIMARY while members are replaced. Keep `mongodb.replicaCount`, `mongodb.replicaSetName`, and `mongodb.mode` unchanged during the upgrade.

!!!warning "Wait for the inventory Job to be removed"
    The inventory Job has an immutable Pod template. Enabling MongoDB authentication changes that template to include the MongoDB credentials. If the previous inventory Job still exists, the upgrade fails with `spec.template: field is immutable`.

    The inventory Job can be created during installation or configuration updates, including when **Apply changes** is selected in the UI. Before starting the authentication upgrade, wait for the Job to complete, then wait until `<release-name>-splunk-connect-for-snmp-inventory` is no longer listed by `microk8s kubectl get jobs --namespace sc4snmp`.

The transition can take longer than Helm's default timeout. When changing authentication from disabled to enabled, use an additional timeout for the upgrade:

```yaml
microk8s helm3 upgrade --install snmp -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace --timeout 30m
```

The transition timeout defaults to `mongodb.replicaCount * mongodb.replicaInitJob.timeout`, which is 30 minutes with the default values.

### Recover the replica set after disabling authentication

If every MongoDB member reports `Does not have a valid replica set config` after changing `mongodb.auth.enabled` from `true` to `false`, wait for the MongoDB rollout to finish:

```bash
microk8s kubectl rollout status statefulset/<release-name>-mongodb --namespace <namespace> --timeout=10m
```

Confirm that every MongoDB Pod runs without `--keyFile`:

```bash
for POD in $(microk8s kubectl get pods --namespace <namespace> -l app=<release-name>-mongodb -o name)
do
  microk8s kubectl get "$POD" --namespace <namespace> -o jsonpath='{.spec.containers[?(@.name=="mongodb")].args}{"\n"}'
done
```

Get the MongoDB DNS domain and force the existing configuration to use the Pod FQDNs. Run the reconfiguration from Pod 0 only:

```bash
MONGODB_FQDN=$(microk8s kubectl exec --namespace <namespace> <release-name>-mongodb-0 -c mongodb -- hostname -f)
MONGODB_DOMAIN=${MONGODB_FQDN#*.}

microk8s kubectl exec --namespace <namespace> <release-name>-mongodb-0 -c mongodb -- \
  mongosh --quiet --eval "
    const config = db.getSiblingDB('local').system.replset.findOne()
    config.members.forEach(member => {
      member.host = '<release-name>-mongodb-' + member._id + '.${MONGODB_DOMAIN}:27017'
    })
    printjson(rs.reconfig(config, { force: true }))
  "
```

After the command returns `ok: 1`, verify that MongoDB elects one PRIMARY and the remaining members become SECONDARY:

```bash
microk8s kubectl exec --namespace <namespace> <release-name>-mongodb-0 -c mongodb -- \
  mongosh --quiet --eval \
  'rs.status().members.forEach(member => print(member.name + " " + member.stateStr + " health=" + member.health))'
```

### Migration from Bitnami MongoDB

The chart automatically detects and migrates data from existing Bitnami MongoDB deployments only in standalone mode:

1. Detects Bitnami PVC: datadir-<release>-mongodb-0
2. Reuses the PVC if found (preserves data)
3. Init container fixes file permissions for compatibility
4. If no existing PVC is found, creates a new one

No manual intervention required - simply upgrade your deployment with the new chart.

!!!warning
    Migration between Bitnami MongoDB and the new chart is possible only to standalone mode. For using replication mode, please reinstall SC4SNMP with a fresh MongoDB deployment.

### Replica Set Initialization

When deploying in replication mode, the chart automatically:

1. Deploys a headless service for stable pod DNS
2. Creates all MongoDB pods with replica set configuration
3. Runs a Kubernetes Job to initialize the replica set
4. Waits for PRIMARY election (typically 10-15 seconds)

The initialization job:

1. Waits for all pods to be ready
2. Verifies network connectivity between pods
3. Runs rs.initiate() from inside pod-0
4. Is idempotent (safe to re-run)

You can monitor initialization progress:

```bash
kubectl logs -f job/<release-name>-mongodb-init-rs -n <namespace>
```

#### Adjusting the timeout:

For clusters with slow storage provisioning or network latency, you may need to increase the timeout:

```yaml
mongodb:
  replicaInitJob:
    timeout: 600 
```

#### Using a different kubectl image

If your environment requires a specific kubectl version or image source:

```yaml
mongodb:
  replicaInitJob:
    image:
      repository: "alpine/kubectl"
      tag: "1.36.3"
```

!!!note
    The kubectl image must include a POSIX shell (/bin/sh) and kubectl binary. Distroless images are not supported.
