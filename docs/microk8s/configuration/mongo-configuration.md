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

  # Replica set configuration (used only when mode = "replication")
  replicaCount: 3
  replicaSetName: rs0

  # Authentication
  auth:
    enabled: false
    rootUser: "admin"
    rootPassword: ""                  # Set if auth.enabled: true
    existingUserSecret: ""            # Or reference existing secret
    rootUserKey: "root-user"
    rootPasswordKey: "root-password"

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
```

| Key                                        | Type   | Default        | Description                                                      |
|--------------------------------------------|--------|----------------|------------------------------------------------------------------|
| mongodb.mode                               | string | standalone     | Deployment mode (standalone or replication).                     |
| mongodb.replicaCount                       | int    | 3              | Number of MongoDB pods (used only in replication mode).          |
| mongodb.replicaSetName                     | string | rs0            | Internal replica set identifier (used only in replication mode). |
| mongodb.auth.enabled                       | bool   | true           | Enable MongoDB authentication.                                   |
| mongodb.auth.rootUser                      | string | admin          | Root username for MongoDB.                                       |
| mongodb.auth.rootPassword                  | string | ""             | Root password (avoid committing; prefer secret).                 |
| mongodb.auth.existingUserSecret            | string | ""             | Name of existing Kubernetes Secret providing credentials.        |
| mongodb.auth.rootUserKey                   | string | root-user      | Key inside existing secret containing the username.              |
| mongodb.auth.rootPasswordKey               | string | root-password  | Key inside existing secret containing the password.              |
| mongodb.image.repository                   | string | mongo          | Container image repository.                                      |
| mongodb.image.tag                          | string | 8.2.2          | Image tag / MongoDB version.                                     |
| mongodb.image.pullPolicy                   | string | IfNotPresent   | Image pull policy.                                               |
| mongodb.resources.requests.cpu             | string | ""             | Guaranteed minimum CPU.                                          |
| mongodb.resources.requests.memory          | string | ""             | Guaranteed minimum memory.                                       |
| mongodb.resources.limits.cpu               | string | ""             | CPU limit.                                                       |
| mongodb.resources.limits.memory            | string | ""             | Memory limit.                                                    |
| mongodb.persistence.enabled                | bool   | true           | Create PersistentVolumeClaim.                                    |
| mongodb.persistence.storageClassName       | string | ""             | StorageClass for the PVC (empty = default).                      |
| mongodb.persistence.accessMode             | string | ReadWriteOnce  | PVC access mode.                                                 |
| mongodb.persistence.size                   | string | 10Gi           | Requested persistent volume size.                                |
| mongodb.podSecurityContext.fsGroup         | int    | 999            | FS group owning mounted volumes.                                 |
| mongodb.containerSecurityContext.runAsUser | int    | 999            | UID for the container (non-root hardening).                      |
| mongodb.replicaInitJob.image.repository    | string | alpine/kubectl | Container image for the initialization job.                      |
| mongodb.replicaInitJob.image.tag           | string | 1.34.2         | Image tag / kubectl version.                                     |
| mongodb.replicaInitJob.timeout             | int    | 600            | Maximum time (in seconds) to wait for each pod to become ready.  |

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
kubectl create secret generic prod-mongodb-secret -n <namespace> \
  --from-literal=root-user='admin' \
  --from-literal=root-password='your_secure_password_here'
```

Then reference it in `values.yaml`:

```yaml
mongodb:
  auth:
    enabled: true
    existingUserSecret: "prod-mongodb-secret"
```

The secret keys (`root-user` and `root-password`) are configurable via `rootUserKey` and `rootPasswordKey` if your secret uses different key names:

```yaml
mongodb:
  auth:
    enabled: true
    existingUserSecret: "prod-mongodb-secret-with-different-keys"
    rootUserKey: "my-username-key"
    rootPasswordKey: "my-password-key"
```


### Migration from Bitnami MongoDB

The chart automatically detects and migrates data from existing Bitnami MongoDB deployments only in standalone mode:

1. Detects Bitnami PVC: datadir-<release>-mongodb-0
2. Reuses the PVC if found (preserves data)
3. Init container fixes file permissions for compatibility
4. If no existing PVC is found, creates a new one

No manual intervention required — simply upgrade your deployment with the new chart.

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
      tag: "1.34.2"
```

!!!note
    The kubectl image must include a POSIX shell (/bin/sh) and kubectl binary. Distroless images are not supported.