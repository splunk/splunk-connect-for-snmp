# Redis configuration

Redis serves as the message broker and task scheduler for SC4SNMP, managing periodic tasks and queueing operations such as SNMP Walk and Poll. It is a critical component for coordinating work between the scheduler, poller, and sender services.

!!!note
    Previously, Redis in our stack was provided via the Bitnami Helm chart. As Bitnami transitions certain components to a paid model, we have replaced it with our own Kubernetes manifests, implementing the necessary deployment logic in-house.
    This change ensures we maintain full control over configuration, compatibility, and licensing. If you encounter any issues or identify missing configuration options, please open an issue in the project repository so we can address it promptly.

### Redis configuration file

Redis configuration is maintained in the `redis` section of `values.yaml`, which is used during installation to configure Kubernetes resources.

```yaml
redis:
  # Mode selector: "standalone", "replication"
  architecture: standalone

  # Authentication
  auth:
    enabled: false
    password: ""                      # Set if auth.enabled: true
    existingSecret: ""                # Or reference existing secret
    existingSecretPasswordKey: "password"

  # Image
  image:
    repository: redis
    tag: "8.2.2"
    pullPolicy: IfNotPresent

  # Resources
  resources:
    requests:
      cpu: 250m
      memory: 256Mi
    limits:
      cpu: 500m
      memory: 512Mi

  # Storage
  storage:
    enabled: true
    storageClassName: microk8s-hostpath
    accessModes:
      - ReadWriteOnce
    size: 5Gi
  persistence:
    aof:
      enabled: true
      fsync: everysec
      
  # Security
  podSecurityContext:
    runAsUser: 999
    fsGroup: 999
```

| Key                                      | Type   | Default             | Description                                                                             |
|------------------------------------------|--------|---------------------|-----------------------------------------------------------------------------------------|
| redis.architecture                       | string | `standalone`        | Deployment mode (standalone or replication).                                            |
| redis.replicas                           | int    | `3`                 | Data pod count (used only in replication mode).                                         |
| redis.sentinel.replicas                  | int    | `3`                 | Sentinel pod count (odd recommended).                                                   |
| redis.sentinel.quorum                    | int    | `2`                 | Required Sentinel votes for failover.                                                   |
| redis.sentinel.resources.requests.cpu    | string | `50m`               | Guaranteed Sentinel minimum CPU.                                                        |
| redis.sentinel.resources.requests.memory | string | `64Mi`              | Guaranteed Sentinel minimum memory.                                                     |
| redis.sentinel.resources.limits.cpu      | string | `100m`              | Guaranteed Sentinel minimum CPU.                                                        |
| redis.sentinel.resources.limits.memory   | string | `128Mi`             | Guaranteed Sentinel minimum memory.                                                     |
| redis.auth.enabled                       | bool   | `false`             | Enable Redis AUTH.                                                                      |
| redis.auth.password                      | string | `""`                | Password when AUTH enabled (avoid committing; prefer secret).                           |
| redis.auth.existingSecret                | string | `""`                | Name of existing Kubernetes Secret providing the password.                              |
| redis.auth.existingSecretPasswordKey     | string | `password`          | Key inside the existing secret containing the password.                                 |
| redis.image.repository                   | string | `redis`             | Container image repository.                                                             |
| redis.image.tag                          | string | `8.2.2`             | Image tag / Redis version.                                                              |
| redis.image.pullPolicy                   | string | `IfNotPresent`      | Image pull policy.                                                                      |
| redis.resources.requests.cpu             | string | `250m`              | Guaranteed minimum CPU.                                                                 |
| redis.resources.requests.memory          | string | `256Mi`             | Guaranteed minimum memory.                                                              |
| redis.resources.limits.cpu               | string | `500m`              | CPU limit.                                                                              |
| redis.resources.limits.memory            | string | `512Mi`             | Memory limit.                                                                           |
| redis.storage.enabled                    | bool   | `true`              | Create PersistentVolumeClaim.                                                           |
| redis.storage.storageClassName           | string | `microk8s-hostpath` | StorageClass for the PVC.                                                               |
| redis.storage.accessModes                | list   | `[ReadWriteOnce]`   | PVC access modes.                                                                       |
| redis.storage.size                       | string | `5Gi`               | Requested persistent volume size.                                                       |
| redis.persistence.aof.enabled            | bool   | `true`              | Enable Append Only File persistence.                                                    |
| redis.persistence.aof.fsync              | string | `everysec`          | AOF fsync policy (`always`, `everysec`, `no`). Necessary to migrate from bitnami Redis. |
| redis.podSecurityContext.runAsUser       | int    | `999`               | UID for the container (non-root hardening).                                             |
| redis.podSecurityContext.fsGroup         | int    | `999`               | FS group owning mounted volumes.                                                        |


### Use authentication for Redis

By default, Redis authentication is disabled. To enable it, choose one of the following methods:

#### Plain text password

Set the password directly in `values.yaml`:

```yaml
redis:
  auth:
    enabled: true
    password: "your_password_here"
```

#### Kubernetes Secret password

To use a Kubernetes Secret for the Redis password, first create a secret with the desired password:

```bash
microk8s kubectl create secret generic prod-redis-secret -n <namespace> --from-literal=password="your_password_here"
```

!!!note
    Replace `<namespace>` with the appropriate namespace where SC4SNMP is deployed.
    `--from-literal` key is `password` because it is the default value of `existingSecretPasswordKey` in `values.yaml`.
    If you want to use a different key, you can specify it in the `values.yaml` file by modifying the `existingSecretPasswordKey` field.

Then, modify the `values.yaml` file to reference this secret:

```yaml
redis:
  auth:
    enabled: true
    existingSecret: "prod-redis-secret"
```
!!!warning
    For smoother migration, it's better to create a new secret with the updated values and then update your configuration to reference this new secret, rather than modifying an existing secret in place.
    
    When changing the content of a Kubernetes Secret that is already in use, the running pods will not automatically pick up the new values. You must recreate the pods for them to use the updated secret.

### Migration from Bitnami Redis

The chart automatically detects and migrates data from existing Bitnami Redis deployments:

1. Detects Bitnami PVC: `redis-data-<release>-redis-master-0`
2. Reuses the PVC if found (preserves data)
3. Init container fixes file permissions for compatibility
4. If no existing PVC is found, creates a new one

No manual intervention required — simply upgrade your deployment with the new chart.

