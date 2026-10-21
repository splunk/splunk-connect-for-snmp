# SC4SNMP failure modes

Pick the section matching the symptom and follow its links to [operator commands](operator-commands.md). Do the [runtime and names](operator-commands.md#runtime-and-names) setup once. Settings are written as `values.yaml` key / `.env` variable; redeploy after every change ([how](operator-commands.md#apply-a-configuration-change)).

## Pods or containers unhealthy

**Ask for:** pod or container status and the events or exit state of the failing component.

1. Run [pod and container status](operator-commands.md#pod-and-container-status). A component is unhealthy when STATUS is not `Running`/`Up`, READY is not complete, or RESTARTS keeps increasing.
2. Read the reason in the pod events or container state, then read its [logs](operator-commands.md#logs-by-component), including the previous container's logs after a crash.

| Evidence | Next check or fix |
|---|---|
| `CreateContainerConfigError` | A referenced Secret does not exist yet, usually the HEC `splunk.tokenSecretRef` Secret. Create or sync it; pods start once it exists. |
| `ErrImagePull` / `ImagePullBackOff` with `i/o timeout` | The node cannot reach the registry. For offline installs, import the images with `microk8s ctr image import` and set `pullPolicy: "Never"`. |
| `Pending`, or MongoDB/Redis restarting while workers autoscale | Resources are exhausted. Check [resource usage](operator-commands.md#resource-usage), then lower worker `maxReplicas` or add capacity. |
| HPA `TARGETS` shows `<unknown>/80%` | `metrics-server` add-on is not enabled; see [MicroK8s add-ons or installation steps missing](#microk8s-add-ons-or-installation-steps-missing). |
| `OOMKilled: true` | Raise that component's memory `resources` limit (Compose: `WORKER_*_MEMORY_LIMIT`) or lower its concurrency. |
| MongoDB exits with code `139`, `OOMKilled: false` | See [MongoDB failures](#mongodb-failures). |
| Compose containers `restarting` right after the first start | Wait about 30 seconds and check again; services start in dependency order. |

Docs: [worker configuration](https://splunk.github.io/splunk-connect-for-snmp/main/configuration/workers/), [Splunk configuration](https://splunk.github.io/splunk-connect-for-snmp/main/configuration/splunk-configuration/), [offline MicroK8s](https://splunk.github.io/splunk-connect-for-snmp/main/microk8s/offlineinstallation/offline-microk8s/), [deploy and run with Compose](https://splunk.github.io/splunk-connect-for-snmp/main/dockercompose/11-deploy-and-run/), [kubectl commands](https://splunk.github.io/splunk-connect-for-snmp/main/troubleshooting/k8s-commands/), [docker commands](https://splunk.github.io/splunk-connect-for-snmp/main/troubleshooting/docker-commands/).

## No data in Splunk

**Ask for:** which index is empty (events, metrics, or both), the [HEC check](operator-commands.md#hec-check) result, and worker-sender log lines containing `ERROR` or `failed`.

Work down the pipeline and stop at the first failing step:

1. **HEC accepts events from the SC4SNMP host.** Run the [HEC check](operator-commands.md#hec-check).
   - A connection, TLS, or resolution error is between the host and Splunk: check the HEC URL, protocol, port, CA trust, and [DNS](#dns-ipv6-and-dual-stack). Use `splunk.insecureSSL` / `SPLUNK_HEC_INSECURESSL` only briefly to confirm a CA problem.
   - `Invalid token`, `Incorrect index`, or `Token disabled` responses belong to the Splunk admin; see [external owner handoffs](escalation-handoff.md#external-owner-handoffs).
2. **All components are healthy.** Otherwise see [pods or containers unhealthy](#pods-or-containers-unhealthy).
3. **The walk was scheduled and succeeded.** Use the walk [Splunk searches](operator-commands.md#splunk-searches) or grep the scheduler and worker-poller [logs](operator-commands.md#logs-by-component) for the device address.
   - No `Sending due task sc4snmp;<ip>:<port>;walk`: see [walks never scheduled](#walks-never-scheduled-or-inventory-updates-fail) and [device not polled](#device-not-polled-or-profile-not-applied).
   - `retry` or `raised unexpected`: see [walk errors](#walk-errors-or-slow-walks).
4. **Polls run.** Polling starts only after the first successful walk, so wait one walk cycle after adding a device.
5. **worker-sender delivers.** Look for `splunk_connect_for_snmp.splunk.tasks.send` failures and HTTP errors in worker-sender logs.
6. **The search looks in the right place.** Numeric data goes to the metrics index (`| mpreview index=netmetrics`), text data and traps to the events index (`index=netops`). Check the configured indexes in `values.yaml` `splunk` / `.env` `SPLUNK_HEC_INDEX_EVENTS` and `SPLUNK_HEC_INDEX_METRICS`.
7. **Metrics through an OpenTelemetry collector HEC receiver are rejected** because of hyphens in names such as `sc4snmp.IF-MIB.ifInOctets`: set `poller.splunkMetricNameHyphenToUnderscore: true` / `SPLUNK_METRIC_NAME_HYPHEN_TO_UNDERSCORE=true`.
8. **mTLS to HEC:** repeat the HEC check with the client certificate flags and `-vvv`, then check worker-sender logs.

Docs: [Splunk requirements](https://splunk.github.io/splunk-connect-for-snmp/main/microk8s/splunk-requirements/), [configuring logs and searches](https://splunk.github.io/splunk-connect-for-snmp/main/troubleshooting/configuring-logs/), [SNMP data format](https://splunk.github.io/splunk-connect-for-snmp/main/configuration/snmp-data-format/), [general issues](https://splunk.github.io/splunk-connect-for-snmp/main/troubleshooting/general-issues/), [mTLS](https://splunk.github.io/splunk-connect-for-snmp/main/mtls/).

## Walk errors or slow walks

**Ask for:** worker-poller log lines for the device address showing the `retry` or `raised unexpected` message, and the device's inventory row (community and secret redacted).

The walk log line looks like `Task splunk_connect_for_snmp.snmp.tasks.walk[<id>] retry: Retry in <n>s: SnmpActionError('An error of SNMP isWalk=True for a host <ip> occurred: <reason>')`. Match the reason:

| Reason or symptom | Cause | Fix |
|---|---|---|
| `Empty SNMP response message` | The agent returns empty varbinds, so the walk keeps retrying and the device is never polled. | `worker.ignoreEmptyVarbinds: true` / `IGNORE_EMPTY_VARBINDS=true` |
| `OID not increasing` | Agent bug in GETBULK ordering. | Add the device to `worker.ignoreNotIncreasingOid` / `IGNORE_NOT_INCREASING_OIDS` (comma-separated). `ip` covers every port on that host; `ip:port` covers one device. |
| `No SNMP response received before timeout` | Wrong IP or port, wrong v2c community, wrong v3 privacy key, or the device is unreachable. | Run [device reachability](operator-commands.md#device-reachability) from the SC4SNMP host. If it fails with verified credentials, hand off to the device or network owner. For v3, see [SNMPv3 polling authentication errors](#snmpv3-polling-authentication-errors). |
| Many `isWalk=True` retries block workers | Unreachable devices hold workers while retrying with exponential backoff. | Lower `worker.walkRetryMaxInterval` / `WALK_RETRY_MAX_INTERVAL` (default 180 seconds) and fix or remove unreachable devices. `worker.walkMaxRetries` / `WALK_MAX_RETRIES` caps attempts. |
| `TooBig` | The agent cannot answer that many OIDs in one request. | Lower `poller.maxOidToProcess` / `MAX_OID_TO_PROCESS` (default 70), or the inventory `max_oid_to_process` column for that device. |
| Walk takes too long or hits `Hard time limit` | The walk scope is too large. | Assign a walk profile with a restricted MIB list, or raise `worker.poller.taskTimeout` / `WORKER_POLLER_TASK_TIMEOUT` (default 2400 seconds). |
| Only `SNMPv2-MIB` data arrives from the walk | The default walk scope is `SNMPv2-MIB` only. | Use a walk profile with the needed MIBs, or `poller.enableFullWalk: true` / `ENABLE_FULL_WALK=true`. |

Docs: [polling issues](https://splunk.github.io/splunk-connect-for-snmp/main/troubleshooting/polling-issues/), [walk profile](https://splunk.github.io/splunk-connect-for-snmp/main/configuration/profiles/#walk-profile), [default walk scope](https://splunk.github.io/splunk-connect-for-snmp/main/configuration/poller-configuration/#default-walk-scope), [worker parameters](https://splunk.github.io/splunk-connect-for-snmp/main/microk8s/configuration/values-params-description/).

## Device not polled or profile not applied

**Ask for:** the device's inventory row, the profile and group definitions it uses (redacted), and inventory job logs from the last change.

1. Check the [inventory job](operator-commands.md#inventory-job) logs for `The following profiles have invalid configuration and won't be used: [...]` or the same message for groups. Fix indentation or keyword spelling in those profiles or groups.
2. Check the inventory row:
   - The header line `address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,max_oid_to_process,delete` must be present.
   - Every name in `profiles` must exactly match a defined profile; an unknown name means the device is not polled.
   - `walk_interval` must be between `1800` and `604800`.
   - `delete` must not be `true`.
3. If the host is also a member of a group in the inventory, the group's settings win and the single-host row is ignored.
4. Check timing:
   - Changes take up to 1 minute to propagate.
   - A changed frequency or profile type applies only after the next walk.
   - The inventory job allows one update per 5 minutes.
5. With the UI enabled, file-based inventory and profiles are ignored; see [configuration change has no effect](#configuration-change-has-no-effect).
6. If polls run but late, workers are saturated. Check [resource usage](operator-commands.md#resource-usage) and the poll task backlog, then add worker-poller and worker-sender replicas or enable autoscaling.
7. Counter graphs that drop to zero periodically are 32-bit counter rollover. Poll the 64-bit counters (for example `ifHCInOctets` instead of `ifInOctets`) where the device supports them.

Docs: [inventory](https://splunk.github.io/splunk-connect-for-snmp/main/configuration/inventory/), [profiles](https://splunk.github.io/splunk-connect-for-snmp/main/configuration/profiles/), [groups](https://splunk.github.io/splunk-connect-for-snmp/main/configuration/groups/), [polling issues](https://splunk.github.io/splunk-connect-for-snmp/main/troubleshooting/polling-issues/), [polling delay](https://splunk.github.io/splunk-connect-for-snmp/main/configuration/workers/#real-life-scenario-i-have-a-significant-delay-in-polling).

## SNMPv3 polling authentication errors

**Ask for:** the exact error line, the secret name in the device's inventory row, and the secret's field names (not values).

| Error | Meaning |
|---|---|
| `Unknown USM user` | The username in the secret does not exist on the device. |
| `Wrong SNMP PDU digest` | The authentication key or protocol does not match. |
| `No SNMP response received before timeout` with a reachable device | Often a wrong privacy key or protocol. |
| Data arrives without auth or privacy, or the device rejects requests without a clear error | `authProtocol` or `privProtocol` is unset or not a supported value, so SC4SNMP falls back to no authentication or no privacy. |

1. Confirm the secret is listed in `poller.usernameSecrets` (MicroK8s), or that `ENABLE_WORKER_POLLER_SECRETS=true` and it is present in `secrets.json` (Compose).
2. Confirm the inventory `secret` column names that secret.
3. Run [SNMPv3 secrets](operator-commands.md#snmpv3-secrets) to see the stored fields. The user compares values locally against the device configuration and does not paste them.
4. Confirm the same credentials with a v3 `snmpget` in [device reachability](operator-commands.md#device-reachability).
5. Recreate the secret with corrected values and redeploy. On Compose, run `docker compose up -d --force-recreate` for the workers.

Docs: [SNMPv3 configuration (MicroK8s and Compose)](https://splunk.github.io/splunk-connect-for-snmp/main/configuration/snmpv3/), [polling issues](https://splunk.github.io/splunk-connect-for-snmp/main/troubleshooting/polling-issues/).

## Traps missing or rejected

**Ask for:** the address and port the agents send to, the [trap endpoint](operator-commands.md#trap-endpoint) output, and traps pod or container logs from a test trap.

1. Confirm the agents target the right endpoint: on MicroK8s, the trap service `EXTERNAL-IP` and its port; on Compose, the host IP and `TRAPS_PORT`. An `EXTERNAL-IP` of `<pending>` means metallb has no address for it; check `traps.loadBalancerIP` and whether metallb is enabled (see [MicroK8s add-ons or installation steps missing](#microk8s-add-ons-or-installation-steps-missing)).
2. Send a test trap from the SC4SNMP host ([device reachability](operator-commands.md#device-reachability)). If the test trap arrives but device traps do not, hand off to the network or device owner.
3. Match the traps log line `ERROR Security Model failure for device ('<ip>', <port>): <reason>`:

| Reason | Fix |
|---|---|
| `Unknown SNMP community name encountered` | Add the community: MicroK8s `traps.communities` in `values.yaml` (`2c: [public]`); Compose `communities` in `traps-config.yaml`. |
| `Unknown SNMP security name encountered` | Wrong username or engine ID. Add the secret: MicroK8s `traps.usernameSecrets` in `values.yaml`; Compose `usernameSecrets` in `traps-config.yaml`. Then set the device's engine ID: MicroK8s `traps.securityEngineId` in `values.yaml`; Compose `SNMP_V3_SECURITY_ENGINE_ID` in `.env`. |
| `Authenticator mismatched` | Wrong authentication protocol or key in the secret. |
| `Ciphering services not available or ciphertext is broken` | Wrong privacy protocol or key in the secret. |

4. For many v3 agents with unknown engine IDs, `traps.discoverEngineId: "true"` / `DISCOVER_ENGINE_ID=true` registers engine IDs for known usernames. Enable it only during initial setup, then turn it off.
5. Traps configuration changes need a restart of the trap deployment ([apply a configuration change](operator-commands.md#apply-a-configuration-change)).
6. Very large traps slow MIB resolution: cap them with `traps.maxVarbindsToDecode` / `MAX_TRAP_VARBINDS_TO_DECODE` (a warning is logged when varbinds are dropped).
7. Unresolved varbinds missing from events: enable `worker.trap.enableIncludeUnresolvedVarbinds` / `INCLUDE_UNRESOLVED_TRAP_VARBINDS`, or add the MIB (see [MIB problems](#mib-and-unresolved-oid-problems)).

Docs: [traps issues](https://splunk.github.io/splunk-connect-for-snmp/main/troubleshooting/traps-issues/), [traps configuration](https://splunk.github.io/splunk-connect-for-snmp/main/configuration/traps/), [engine ID discovery](https://splunk.github.io/splunk-connect-for-snmp/main/configuration/traps/#engine-id-discovery).

## Discovery problems

**Ask for:** worker-discovery logs, the discovery configuration (credentials redacted), and the subnet size.

| Evidence | Fix |
|---|---|
| `PermissionError: [Errno 13] Permission denied: '/app/discovery/discovery_devices.csv'` | Make the `discoveryPath` / `DISCOVERY_PATH` host folder writable by UID 10001 (`sudo chown 10001:10001 <path>`). |
| `Hard time limit (2400s) exceeded for splunk_connect_for_snmp.discovery.tasks.discovery` | Raise `worker.discovery.taskTimeout` / `WORKER_DISCOVERY_TASK_TIMEOUT`, or split large subnets. |
| Discovery is slow | Each silent IP costs timeout x retries. Lower `worker.udpConnectionRetries` / `UDP_CONNECTION_RETRIES`; values that are too low miss slow devices. |
| `discovery_devices.csv` is empty | Wrong subnet or port, no SNMP-enabled devices, or wrong v2c/v3 credentials. Verify one device with [device reachability](operator-commands.md#device-reachability). |
| Discovery never runs on Compose | `COMPOSE_PROFILES` must include `discovery`. |
| IPv6 subnets are skipped | Set `discovery.ipv6Enabled: true`. |

Docs: [discovery issues](https://splunk.github.io/splunk-connect-for-snmp/main/troubleshooting/discovery-issues/), [discovery configuration](https://splunk.github.io/splunk-connect-for-snmp/main/configuration/discovery-configuration/).

## Helm install or upgrade errors

**Ask for:** the full `helm upgrade` command (no `--set` secrets) and its error output.

| Error | Fix |
|---|---|
| `cannot patch "<release>-splunk-connect-for-snmp-inventory" with kind Job ... field is immutable` | The previous inventory job still exists (one update per 5 minutes). Wait until the [inventory job](operator-commands.md#inventory-job) disappears, or delete the job, then rerun the upgrade. |
| `spec.template: field is immutable` while enabling MongoDB authentication | Same cause: wait for the inventory job to be removed before the upgrade. |
| Render fails while `UI.auth.enabled: true` | `UI.auth.existingSecret` is required when UI authentication is on. |
| YAML parse errors, or settings silently ignored | Validate `values.yaml` with `yamllint` ([configuration](operator-commands.md#configuration-redacted)); check indentation and key spelling against the parameter reference. |
| Upgrade installed an unexpected version | Compare the installed and latest versions ([version](operator-commands.md#version)); run `microk8s helm3 repo update` before upgrading. |

Docs: [polling issues](https://splunk.github.io/splunk-connect-for-snmp/main/troubleshooting/polling-issues/), [installation](https://splunk.github.io/splunk-connect-for-snmp/main/microk8s/sc4snmp-installation/), [upgrade](https://splunk.github.io/splunk-connect-for-snmp/main/microk8s/upgrade/), [values parameters](https://splunk.github.io/splunk-connect-for-snmp/main/microk8s/configuration/values-params-description/), [enable the UI](https://splunk.github.io/splunk-connect-for-snmp/main/microk8s/gui/enable-gui/).

## MicroK8s add-ons or installation steps missing

Use this branch when SC4SNMP cannot even install cleanly, or when a symptom elsewhere traces back to a missing MicroK8s add-on rather than SC4SNMP configuration.

**Ask for:** whether this is a single node or a cluster, and the output of [MicroK8s add-ons](operator-commands.md#microk8s-add-ons).

This skill identifies which required add-on or installation step is missing and points to the install guide. Setting up the MicroK8s cluster itself — node sizing, joining nodes, choosing a metallb IP pool, or offline or proxy installation — is outside this skill; that belongs to whoever owns the MicroK8s platform, using the install guide below.

| Add-on or step | What breaks when it's missing | Safe to name as a fix? |
|---|---|---|
| `helm3` | `microk8s helm3` commands fail; SC4SNMP cannot be installed or upgraded. | Yes: `microk8s enable helm3`. |
| `rbac` | Pods fail with permission-denied events, or ServiceAccount/Role creation errors during install. | Yes: `microk8s enable rbac`. |
| `metrics-server` | HPA `TARGETS` shows `<unknown>/80%`; see [pods or containers unhealthy](#pods-or-containers-unhealthy). | Yes: `microk8s enable metrics-server`. |
| `hostpath-storage` or `openebs` | MongoDB and Redis PVCs stay `Pending`; `get storageclass` is empty. | No. The choice between `hostpath-storage` and `openebs` (and the resulting `storageClass` / `storageClassName` values) is a production-sizing decision; point to the install guide. |
| `metallb` | The trap service `EXTERNAL-IP` stays `<pending>`; see [traps missing or rejected](#traps-missing-or-rejected). | No. Enabling it requires choosing an IP pool from the customer's network; point to the install guide. |
| `dns` (CoreDNS) | Pods cannot resolve internal services or the Splunk host; see [DNS, IPv6, and dual-stack](#dns-ipv6-and-dual-stack). | No. It is usually preinstalled; re-enabling it needs resolver IP addresses from the customer; point to the install guide. |
| `sudo systemctl enable iscsid` not run | `openebs` volumes fail to attach. | No, this is a one-time host setup step from the install guide. |
| User never added to the `microk8s` group | Every command needs `sudo`, which can mask or duplicate issues if some steps ran as a different user. | No, point to the install guide. |

For the three single-command add-ons (`helm3`, `rbac`, `metrics-server`), naming the missing add-on and its enable command is enough. For everything else in the table, name what is missing and link the install guide instead of choosing values (an IP pool, resolver addresses, a storage class, node topology) on the customer's behalf.

Docs: [MicroK8s add-ons and installation](https://splunk.github.io/splunk-connect-for-snmp/main/microk8s/mk8s/k8s-microk8s/), [SC4SNMP installation](https://splunk.github.io/splunk-connect-for-snmp/main/microk8s/sc4snmp-installation/), [cluster scaling](https://splunk.github.io/splunk-connect-for-snmp/main/microk8s/mk8s/k8s-microk8s-scaling/), [enable IPv6](https://splunk.github.io/splunk-connect-for-snmp/main/microk8s/enable-ipv6/).

## Configuration change has no effect

**Ask for:** what was changed, how it was applied, and whether `UI.enable` is `true`.

1. **UI enabled.** When `UI.enable: true`, the inventory, profiles, and groups are read from MongoDB, not from `values.yaml`. On the first deploy with the UI enabled they are copied from the files once; after that, `helm upgrade`, `--set-file`, and inline edits to `poller.inventory`, `scheduler.profiles`, and `scheduler.groups` have no effect.
   - Make those changes in the UI and click **Apply changes**. Updates are allowed once every 5 minutes, and job creation is retried while the previous inventory job exists.
   - **Restore configuration** reloads all three from the deployment files and discards UI edits. It cannot be undone, so confirm with the user first.
   - If automation must own the inventory, set `UI.enable: false` and upgrade. The inventory job then drops the UI copies (`inventory_ui`, `profiles_ui`, `groups_ui` in MongoDB) and loads the files again. Copy any UI-only edits into the files first.
   - Every other setting (workers, resources, images, Splunk, MongoDB, Redis) still comes from `values.yaml` and `helm upgrade`.
2. **Secrets rotated.** HEC tokens, Redis passwords, and other Secrets are read at pod start. Restart the affected deployments after updating the Secret.
3. **Traps settings.** Restart the trap deployment after changing them.
4. **Compose.** `docker compose up -d` does not recreate containers whose definition did not change. Use `docker compose up -d --force-recreate` after editing mounted files or secrets.
5. **Profiles or frequency.** These apply only after the next walk; see [device not polled](#device-not-polled-or-profile-not-applied).

Docs: [UI apply changes](https://splunk.github.io/splunk-connect-for-snmp/main/microk8s/gui/apply-changes/), [Splunk configuration](https://splunk.github.io/splunk-connect-for-snmp/main/configuration/splunk-configuration/), [Redis configuration](https://splunk.github.io/splunk-connect-for-snmp/main/microk8s/configuration/redis-configuration/), [traps configuration](https://splunk.github.io/splunk-connect-for-snmp/main/configuration/traps/).

## Walks never scheduled or inventory updates fail

Use this branch when walks stop for many devices, or when every `helm upgrade` or **Apply changes** run fails in the inventory job while polls for other devices continue.

**Ask for:** the inventory job logs from the last update, scheduler logs, the number of devices in the inventory, and the output of the read-only [Redis schedules](operator-commands.md#redis-schedules) counts.

1. Search the scheduler logs or Splunk for `Sending due task sc4snmp;<ip>:<port>;walk`. If it is missing for a device in the inventory, its walk schedule is missing.
2. Run the read-only [Redis schedules](operator-commands.md#redis-schedules) checks:
   - Walk entries should be about the number of devices.
   - `ZCARD redbeat::schedule` should be about devices x (1 walk + number of distinct poll frequencies).
   - Any `redbeat:sc4snmp;*` key without a `definition` field is a corrupted entry. Corrupted entries can make the whole inventory update fail before any device is processed, so missing walks never self-heal.
3. Only after the user confirms, delete the corrupted keys and remove them from `redbeat::schedule` (the deletion block in Redis schedules). Then run one normal `helm upgrade` with unchanged values, or **Apply changes**. The inventory update recreates missing walk schedules. Do not edit every inventory row to force a mass re-walk.
4. Run only one scheduler replica, and do not run scripted upgrades that overlap with a running inventory job. Concurrent schedule rewrites are a known way to leave half-written entries.
5. If tasks are scheduled but expire before a worker picks them up, workers are saturated. Scale the workers, or raise `scheduler.tasksExpiryTime` / `CHAIN_OF_TASKS_EXPIRY_TIME`.

If corrupted entries return after cleanup, escalate with the inventory job logs and the key names ([escalation handoff](escalation-handoff.md)).

Docs: [scheduler configuration](https://splunk.github.io/splunk-connect-for-snmp/main/microk8s/configuration/scheduler-configuration/), [Redis configuration](https://splunk.github.io/splunk-connect-for-snmp/main/microk8s/configuration/redis-configuration/), [configuring logs and searches](https://splunk.github.io/splunk-connect-for-snmp/main/troubleshooting/configuring-logs/).

## MongoDB failures

**Ask for:** MongoDB pod or container logs, its exit code, the host kernel version (`uname -r`), and what changed in `mongodb.*` / `MONGO_*` settings.

| Evidence | Cause and fix |
|---|---|
| Logs show `mongod startup complete`, then about 30 seconds later the container exits with code `139` and `OOMKilled=false`; the next start logs `Detected unclean shutdown - Lock file is not empty` | MongoDB 8.x on a host kernel 6.19 or newer with `glibc.pthread.rseq=0`. SC4SNMP 1.17.0 and later default to `GLIBC_TUNABLES=glibc.pthread.rseq=1`; restore it in `mongodb.extraEnv` / `MONGO_GLIBC_TUNABLES` if it was overridden, or upgrade. |
| Application pods log `Authentication failed` after the MongoDB root password changed, while MongoDB itself is healthy | MongoDB keeps the password from the first initialization. Follow the password rotation procedure using the old password. Reinstalling with PVC deletion is the last resort and loses all data. |
| Members report `Does not have a valid replica set config` after `mongodb.auth.enabled` was changed from `true` to `false` | Follow the replica set recovery procedure; data is kept. |
| Upgrade from 1.12.2 to 1.12.3 fails in the `mongo-fcv-upgrade-to-6` job | Set the feature compatibility version manually (`db.adminCommand({ setFeatureCompatibilityVersion: "6.0" })`) or reinstall with PVC deletion. |
| Enabling authentication on a replica set times out | Use an odd replica count of at least 3 and `--timeout 50m` on the upgrade. |

Never modify or delete the `<release>-mongodb-replicakey` Secret while the replica set is running. Check member health with the [MongoDB](operator-commands.md#mongodb) commands.

Docs: [general issues](https://splunk.github.io/splunk-connect-for-snmp/main/troubleshooting/general-issues/), [MongoDB configuration](https://splunk.github.io/splunk-connect-for-snmp/main/microk8s/configuration/mongo-configuration/), [rotating the MongoDB password](https://splunk.github.io/splunk-connect-for-snmp/main/microk8s/configuration/mongo-configuration/#rotating-the-mongodb-password), [replica set recovery](https://splunk.github.io/splunk-connect-for-snmp/main/microk8s/configuration/mongo-configuration/#recover-the-replica-set-after-disabling-authentication).

## MIB and unresolved OID problems

**Ask for:** the OID or MIB name that is not translated, and mibserver logs since its last restart.

1. Check whether the MIB is in the public MIB repository index (`https://pysnmp.github.io/mibs/index.csv`, or `https://pysnmp.github.io/mibs/asn1/<MIB-NAME>`). If not, load it as a local MIB.
2. For local MIBs, check the [MIB server](operator-commands.md#mib-server) logs:
   - `No local mibs. Skipping...` has three causes:
     - `mibserver.localMibs.pathToMibs` / `LOCAL_MIBS_PATH` is not set.
     - The persistent volume was created after the mibserver pod started; restart the mibserver.
     - The folder layout is wrong; it must be `<path>/<VENDOR>/<MIB_FILE>`.
   - `Illegal character` usually means the MIB files have an extension such as `.txt`. MIB files must be named exactly like the module defined before `::= BEGIN`.
   - Compilation errors name the failing file and line. Broken vendor MIBs must be fixed by the vendor or replaced locally.
3. After adding local MIBs, restart the mibserver. After changing `mibserver.image.tag`, also restart worker-poller and worker-trap.
4. On Compose, the user running Docker needs read and write access to `LOCAL_MIBS_PATH`.

Docs: [MIB request and local MIBs](https://splunk.github.io/splunk-connect-for-snmp/main/mib-request/).

## DNS, IPv6, and dual-stack

**Ask for:** the failing name lookup or connection error, and whether IPv6 or dual-stack is enabled.

1. **Pods cannot resolve internal services or the Splunk host.** Run the [DNS and network](operator-commands.md#dns-and-network) lookups for `<release>-redis.<namespace>` and the HEC host.
   - Internal names fail: CoreDNS is not running or pod-to-DNS traffic is blocked (`no route to host`).
   - External names fail: CoreDNS forwards to unreachable resolvers. Re-enable it with `microk8s enable dns:<dns-ip>,<dns-ip>`, or edit `configmap/coredns` in `kube-system`. Use the CoreDNS configuration for per-domain or reverse zones.
2. **Trap events show IPs instead of hostnames.** Enable `worker.trap.resolveAddress.enabled` / `RESOLVE_TRAP_ADDRESS`. The cache is cleared when the trap worker restarts.
3. **Dual-stack on MicroK8s** needs all of the following:
   - a Calico IPv6 pool with `natOutgoing: true`
   - a metallb pool with an IPv6 range
   - `traps.ipFamilyPolicy: RequireDualStack`
   - `ipv6Enabled: true` on `poller`, `discovery`, `mibserver`, `redis`, and `mongodb`
4. **Dual-stack on Compose:** `IPv6_ENABLED=true`, and `COREDNS_ADDRESS_IPv6` must be inside `IPAM_SUBNET_IPv6` and differ from the gateway. Otherwise Docker fails with `no configured subnet contains IP address`.
5. Hostnames that resolve to both address families are polled over IPv6 first.

Docs: [MicroK8s add-ons and DNS](https://splunk.github.io/splunk-connect-for-snmp/main/microk8s/mk8s/k8s-microk8s/), [CoreDNS configuration](https://splunk.github.io/splunk-connect-for-snmp/main/microk8s/configuration/coredns-configuration/), [enable IPv6 on MicroK8s](https://splunk.github.io/splunk-connect-for-snmp/main/microk8s/enable-ipv6/), [enable IPv6 on Compose](https://splunk.github.io/splunk-connect-for-snmp/main/dockercompose/10-enable-ipv6/), [reverse DNS for traps](https://splunk.github.io/splunk-connect-for-snmp/main/configuration/workers/#reverse-dns-lookup-in-trap-worker).

## Nothing above matches

1. Raise the affected component's log level to `DEBUG`, reproduce once, and collect the logs ([log level](operator-commands.md#log-level)).
2. For SNMP protocol-level detail, use [deep debug](operator-commands.md#deep-debug), which covers pysnmp debug flags and the Flower Celery UI.
3. Revert debug settings, then prepare the [escalation handoff](escalation-handoff.md).
