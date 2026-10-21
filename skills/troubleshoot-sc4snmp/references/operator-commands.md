# SC4SNMP operator commands

Each check gives a MicroK8s and a Docker Compose variant, the expected result, and what the user should return. All checks are read-only unless marked otherwise. Ask the user to redact tokens, community strings, SNMPv3 keys, and passwords before pasting any output.

## Runtime and names

**MicroK8s.** Set these once per shell. Confirm the namespace and release name with the first command.

```bash
microk8s helm3 list -A
NS=sc4snmp
RELEASE=snmp
K="microk8s kubectl -n $NS"
```

- On another Kubernetes distribution, replace `microk8s kubectl` with `kubectl` and `microk8s helm3` with `helm`.
- Deployment names are `$RELEASE-splunk-connect-for-snmp-<component>`, where `<component>` is `scheduler`, `trap`, `worker-poller`, `worker-sender`, `worker-trap`, or `worker-discovery`.
- The inventory job is `$RELEASE-splunk-connect-for-snmp-inventory`.
- Other resources:
  - mibserver: deployment `$RELEASE-mibserver`
  - MongoDB: statefulset `$RELEASE-mongodb`, first pod `$RELEASE-mongodb-0`
  - Redis standalone: pod `$RELEASE-redis-standalone-0`
  - Redis replication mode: pods `$RELEASE-redis-ha-<n>`

**Docker Compose.** Run every command from the `docker_compose` directory that contains `docker-compose.yaml` and `.env`.

- Fixed container names: `sc4snmp-scheduler`, `sc4snmp-traps`, `sc4snmp-inventory`, `sc4snmp-discovery`, `snmp-mibserver`, `mongo`, `redis`, `coredns`.
- Workers are scaled services named `<project>-worker-poller-<n>`, for example `docker_compose-worker-poller-1`. The same pattern applies to `worker-sender`, `worker-trap`, and `worker-discovery`.
- Use `docker compose logs <service>` to read all replicas of a service at once.

## Version

```bash
# MicroK8s
microk8s helm3 list -n $NS          # installed CHART and APP VERSION
microk8s helm3 search repo snmp     # latest version in the local repo cache
$K get pods -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{range .spec.containers[*]}{.image}{" "}{end}{"\n"}{end}'
microk8s version
microk8s kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.nodeInfo.kernelVersion}{"\n"}{end}'
```

```bash
# Docker Compose
grep -E '^(SC4SNMP_TAG|MIBSERVER_TAG|MONGO_TAG|REDIS_TAG)=' .env
sudo docker ps --format '{{.Names}}\t{{.Image}}'
docker compose version              # 2.23.1 or later is required
uname -r
```

**Expected:** every SC4SNMP container uses the same `ghcr.io/splunk/splunk-connect-for-snmp/container:<version>` tag.

**Return:** the installed version, the runtime version, and the kernel version.

## Apply a configuration change

These commands change the deployment. Use them only after the user agrees to the change.

```bash
# MicroK8s: pin --version to the installed chart version to avoid an unplanned upgrade
microk8s helm3 upgrade --install $RELEASE -f values.yaml splunk-connect-for-snmp/splunk-connect-for-snmp \
  --namespace=$NS --create-namespace --version <installed-chart-version>
$K rollout restart deployment $RELEASE-splunk-connect-for-snmp-trap   # after traps settings change
$K rollout restart deployment <deployment-name>                      # after a referenced Secret changes
$K get deployments
```

```bash
# Docker Compose
sudo docker compose up -d
sudo docker compose up -d --force-recreate <service>   # mounted files or secrets changed
```

**Expected:** helm reports `has been upgraded`, and the pods roll to `Running`. If helm fails with `field is immutable`, see the [inventory job](#inventory-job).

## Pod and container status

```bash
# MicroK8s
$K get pods -o wide
microk8s kubectl get pods -A        # includes kube-system add-ons: coredns, calico, metallb, metrics-server
$K describe pod <pod-name>          # read Events at the bottom
$K get events --sort-by=.lastTimestamp | tail -30
```

```bash
# Docker Compose
sudo docker compose ps -a
sudo docker inspect <container> --format 'status={{.State.Status}} exit={{.State.ExitCode}} oom={{.State.OOMKilled}} restarts={{.RestartCount}}'
```

**Expected:** every pod is `Running` with READY `n/n`, or every container is `Up`, and restart counts are stable.

**Return:** the status table, plus the Events or inspect line for each failing component.

## MicroK8s add-ons

Add-ons are cluster-wide, so check this once per cluster, not per namespace. Not applicable to Docker Compose or non-MicroK8s Kubernetes.

```bash
microk8s status                         # addon-enabled summary
microk8s kubectl get storageclass       # hostpath-storage or openebs classes
microk8s kubectl get pods -n kube-system | grep -iE 'coredns|calico|metrics-server'
microk8s kubectl get deployment -n metallb-system 2>/dev/null
```

**Expected:** `microk8s status` lists `helm3`, `hostpath-storage` (or `openebs`), `rbac`, `metrics-server`, `dns`, and `metallb` as enabled, and `get storageclass` returns at least one usable class.

**Return:** the `microk8s status` output and the storage class list. See [MicroK8s add-ons or installation steps missing](failure-modes.md#microk8s-add-ons-or-installation-steps-missing) for which gaps are safe to name a one-line fix for, and which need the install guide instead.

## Logs by component

| Symptom | MicroK8s component label | Compose service or container |
|---|---|---|
| Walk or poll errors, SNMPv3 polling errors | `worker-poller` | `worker-poller` |
| Delivery to Splunk | `worker-sender` | `worker-sender` |
| Trap reception and authentication | `trap` | `sc4snmp-traps` |
| Trap processing and translation | `worker-trap` | `worker-trap` |
| Scheduling (`Sending due task`) | `scheduler` | `sc4snmp-scheduler` |
| Inventory, profile, and group loading | `inventory` | `sc4snmp-inventory` |
| Discovery | `worker-discovery` | `worker-discovery` |
| MIB compilation | deployment `$RELEASE-mibserver` | `snmp-mibserver` |

```bash
# MicroK8s: --tail is required with -l, otherwise only 10 lines per pod are shown
$K logs -l app.kubernetes.io/component=worker-poller --prefix --timestamps --tail=2000 | grep '<device-ip>'
$K logs <pod-name> --previous                                   # the container that crashed
$K logs job/$RELEASE-splunk-connect-for-snmp-inventory
$K logs deploy/$RELEASE-mibserver --tail=200
```

```bash
# Docker Compose
sudo docker compose logs --timestamps --tail=2000 worker-poller | grep '<device-ip>'
sudo docker logs --timestamps --tail=500 sc4snmp-traps
```

- If SC4SNMP logs are forwarded to Splunk, search them there instead. On MicroK8s with the Splunk OpenTelemetry Collector, use `index=em_logs sourcetype="kube:container:splunk-connect-for-snmp-<component>"`. On Compose with Splunk logging, use the index set in `SPLUNK_LOG_INDEX`.

**Return:** timestamped lines around the first error, with the device address and task ID.

## Log level

Valid values are `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`, and `FATAL`. The default is `INFO`. The monitoring dashboard needs `INFO` or lower. Revert to `INFO` after reproducing.

| Component | `values.yaml` | `.env` |
|---|---|---|
| All workers (poller, sender, trap, discovery) | `worker.logLevel` | `WORKER_LOG_LEVEL` |
| Scheduler | `scheduler.logLevel` | `SCHEDULER_LOG_LEVEL` |
| Inventory job, including jobs started by UI **Apply changes** | `poller.logLevel` (1.18.0 and earlier: `scheduler.logLevel`) | `INVENTORY_LOG_LEVEL` |
| Trap receiver | `traps.logLevel` | `TRAP_LOG_LEVEL` |
| Discovery | `discovery.logLevel` | `DISCOVERY_LOG_LEVEL` |

Keep `worker.disableMongoDebugLogging` / `WORKER_DISABLE_MONGO_DEBUG_LOGGING` set to `true` unless MongoDB driver logs are needed. Apply with [apply a configuration change](#apply-a-configuration-change).

## Configuration (redacted)

```bash
# MicroK8s: user-supplied values of the running release
microk8s helm3 get values $RELEASE -n $NS > sc4snmp-values.yaml
sed -i -E 's/^([[:space:]]*(token|password|rootPassword|authKey|privKey)[[:space:]]*:).*/\1 <redacted>/I' sc4snmp-values.yaml
yamllint -d '{extends: relaxed, rules: {line-length: disable}}' values.yaml
```

```bash
# Docker Compose
sudo docker compose config --quiet && echo "compose config OK"
grep -vE '(TOKEN|PASSWORD|KEY)=' .env
grep -E '^(INVENTORY|SCHEDULER|TRAPS|DISCOVERY)_CONFIG_FILE_ABSOLUTE_PATH=|^INVENTORY_FILE_ABSOLUTE_PATH=' .env
```

The `sed` command does not cover community strings. The user must also redact the `community` column in inventory rows and the entries under `traps.communities` / `communities` before sharing.

**Return:** only the relevant sections: `poller`, `scheduler`, `worker`, `traps`, `splunk` (without the token), `UI.enable`, `mongodb.mode`, and `redis.architecture`.

## Resource usage

```bash
# MicroK8s
microk8s kubectl top nodes
$K top pods
$K get hpa
```

```bash
# Docker Compose
sudo docker stats --no-stream
```

**Expected:** usage below the `resources` limits, and HPA targets that show percentages rather than `<unknown>`. Workers pinned at their CPU limit, or Pending pods, mean the deployment needs more replicas, or fewer replicas than the node can host.

## Trap endpoint

```bash
# MicroK8s
$K get svc
$K describe svc $RELEASE-splunk-connect-for-snmp-trap
```

```bash
# Docker Compose
grep '^TRAPS_PORT=' .env
sudo docker port sc4snmp-traps
```

**Expected:**
- With metallb, the trap service is a `LoadBalancer` with an `EXTERNAL-IP` (`traps.loadBalancerIP`) and `PORT(S)` like `162:32180/UDP`.
  - Agents normally send to `EXTERNAL-IP` on the service port, the first number (162 by default).
  - The node port, the second number, answers on every node IP. The traps troubleshooting page pairs it with `EXTERNAL-IP`, which works when that address is a node IP.
  - Confirm whichever address and port the agents use with a test trap ([device reachability](#device-reachability)).
- With `traps.service.type: NodePort`, agents send to a node IP and the node port.
- On Compose, agents send to the host IP and `TRAPS_PORT`.

**Return:** the service line or port mapping, and the address and port the agents are configured with.

## Device reachability

Run these from the SC4SNMP host to test the same network path. They require the net-snmp tools (`snmpget`, `snmpwalk`, `snmptrap`). Type credentials directly in the shell; do not paste them back.

```bash
snmpget -v2c -c '<community>' <device-ip>:<port> 1.3.6.1.2.1.1.3.0
snmpget -v3 -l authPriv -u '<user>' -a <authProtocol> -A '<authKey>' -x <privProtocol> -X '<privKey>' <device-ip>:<port> 1.3.6.1.2.1.1.3.0
snmpwalk -v2c -c '<community>' <device-ip>:<port> 1.3.6.1.2.1.1   # SNMPv2-MIB system group
# test trap into SC4SNMP; the community must be listed in traps.communities
snmptrap -v2c -c '<community>' <trap-ip>:<trap-port> 123 1.3.6.1.2.1.1.4 1.3.6.1.2.1.1.4 s test
```

**Expected:** `snmpget` returns `sysUpTime`, and the test trap appears in the traps logs and in `index=netops sourcetype="sc4snmp:traps"`.

- If `snmpget` times out with verified credentials, the device or the network is at fault; see [external owner handoffs](escalation-handoff.md#external-owner-handoffs).
- If `snmpget` works but SC4SNMP fails, compare the credentials and secret used by SC4SNMP.

## HEC check

Run this from the SC4SNMP host. `read -rs` keeps the token out of shell history.

```bash
read -rs HEC_TOKEN
curl https://<hec-host>:8088/services/collector/event \
  -H "Authorization: Splunk $HEC_TOKEN" \
  -d '{"event": "sc4snmp hec test", "index": "netops", "sourcetype": "sc4snmp:test"}'
```

**Expected:** `{"text":"Success","code":0}`. If that works, search `index=netops sourcetype="sc4snmp:test"` to confirm the event arrived.

- A certificate error means the HEC endpoint does not use a CA trusted by the host. Rerun with `-k` only to confirm it.
- `Invalid token`, `Incorrect index`, or `Token disabled` must be fixed by the Splunk admin.
- For mTLS, add `--cert`, `--key`, and `--cacert` with the client certificate paths, and `-vvv` for TLS detail.

**Return:** the response body and HTTP status, never the token.

## SNMPv3 secrets

```bash
# MicroK8s
$K get secrets
$K describe secret <secret-name>     # field names and sizes only, safe to share
```

```bash
# Docker Compose
sudo docker exec docker_compose-worker-poller-1 sh -c 'ls secrets/snmpv3'
sudo docker exec docker_compose-worker-poller-1 sh -c 'ls secrets/snmpv3/<secret-name>'
```

**Expected:**
- The secret exists with `userName`, `authKey`, `authProtocol`, and, for authPriv, `privKey` and `privProtocol`.
- `authProtocol` and `privProtocol` use supported names: `MD5`, `SHA`, `SHA224`, `SHA256`, `SHA384`, `SHA512`; `DES`, `3DES`, `AES`, `AES192`, `AES256`, `AES192BLMT`, `AES256BLMT`.
- The secret is listed in `poller.usernameSecrets` or `traps.usernameSecrets`. On Compose, it is present in `secrets.json`, and `ENABLE_WORKER_POLLER_SECRETS` / `ENABLE_TRAPS_SECRETS` are `true`.

To compare values, the user prints them locally and does not paste them back:

```bash
# MicroK8s
$K get secret <secret-name> -o json | jq '.data | map_values(@base64d)'
# Docker Compose: what the running container loaded
sudo docker exec docker_compose-worker-poller-1 sh -c 'cd secrets/snmpv3/<secret-name> && for f in *; do echo "$f= $(cat "$f")"; done'
```

On Compose, a container started before the last `secrets.json` edit still uses the old values. Compare the two timestamps, then run `sudo docker compose up -d --force-recreate worker-poller worker-trap` if the file is newer:

```bash
sudo docker inspect docker_compose-worker-poller-1 --format '{{.State.StartedAt}}'
ls -l --time-style=full-iso "$(grep '^SECRET_FOLDER_PATH=' .env | cut -d= -f2 | tr -d '"')/secrets.json"
```

**Return:** the `describe` output or the file listing, and whether the values match the device configuration.

## Splunk searches

Replace `index=*` with the index that holds SC4SNMP logs. Add the device address, for example `"10.0.0.1:161"`, or a task ID to narrow the results.

```text
index=* sourcetype="*:container:splunk-connect-for-snmp-*" "Scheduler: Sending due task sc4snmp;*;walk"
index=* sourcetype="*:container:splunk-connect-for-snmp-*" "splunk_connect_for_snmp.snmp.tasks.walk[*] retry"
index=* sourcetype="*:container:splunk-connect-for-snmp-*" "splunk_connect_for_snmp.snmp.tasks.walk[*] succeeded"
index=* sourcetype="*:container:splunk-connect-for-snmp-*" "splunk_connect_for_snmp.snmp.tasks.walk[*] raised unexpected"
index=* sourcetype="*:container:splunk-connect-for-snmp-scheduler*" "Scheduler: Sending due task sc4snmp;*;*;poll"
index=* sourcetype="*:container:splunk-connect-for-snmp-*" "splunk_connect_for_snmp.snmp.tasks.poll[*] failed" "'address': '*'"
index=* sourcetype="*:container:splunk-connect-for-snmp-*" "splunk_connect_for_snmp.snmp.tasks.trap[*] failed"
index=* sourcetype="*:container:splunk-connect-for-snmp-*" splunk_connect_for_snmp.splunk.tasks.send
```

Data checks:

```text
index=netops sourcetype="sc4snmp:event" host="<device-ip>*" earliest=-24h | stats count latest(_time) as last_seen by host
index=netops sourcetype="sc4snmp:traps" earliest=-1h | stats count by host
| mpreview index=netmetrics | search sourcetype="sc4snmp:metric" host="<device-ip>*"
```

The SC4SNMP monitoring dashboard, from `dashboard.xml` on each GitHub release, shows the same walk, poll, trap, and send status over time.

**Return:** result counts and the newest matching line for each query, with the time range and timezone used.

## Inventory job

```bash
# MicroK8s
$K get jobs
$K get pods | grep inventory
$K logs job/$RELEASE-splunk-connect-for-snmp-inventory
# Changes the deployment, only to unblock an urgent upgrade:
$K delete job/$RELEASE-splunk-connect-for-snmp-inventory
```

```bash
# Docker Compose
sudo docker logs --timestamps sc4snmp-inventory
```

**Expected:** the job completes within minutes and disappears about 5 minutes later. Its logs list the loaded devices and contain no `invalid configuration` or traceback lines.

## Redis schedules

The read-only check below counts schedules and lists corrupted entries: RedBeat keys without a `definition` field. Schedules live in Redis database 1.

- In Redis replication mode, run it on the current master. Use the `$RELEASE-redis-ha-<n>` pod whose `INFO replication` shows `role:master`.
- On Compose, run the same script with `sudo docker exec redis sh -c '...'`.

```bash
$K exec $RELEASE-redis-standalone-0 -- sh -c '
  r() { redis-cli ${REDIS_PASSWORD:+-a "$REDIS_PASSWORD"} --no-auth-warning -n 1 "$@"; }
  echo "walk entries:  $(r --scan --pattern "redbeat:sc4snmp;*;walk" | wc -l)"
  echo "poll entries:  $(r --scan --pattern "redbeat:sc4snmp;*;poll" | wc -l)"
  echo "schedule size: $(r ZCARD redbeat::schedule)"
  echo "corrupted entries:"
  r --scan --pattern "redbeat:sc4snmp;*" | while read -r k; do
    [ "$(r HEXISTS "$k" definition)" = 0 ] && echo "  $k"
  done'
```

**Expected:**
- Walk entries are about equal to the number of devices.
- The schedule size is about devices x (1 + number of distinct poll frequencies).
- No corrupted entries are listed.

**Return:** the counts and the list of corrupted keys.

**Write operation:** run this only after the user confirms. It deletes the corrupted entries listed above. Afterwards, run one normal `helm upgrade` or **Apply changes** so the inventory update recreates the missing schedules.

```bash
$K exec $RELEASE-redis-standalone-0 -- sh -c '
  r() { redis-cli ${REDIS_PASSWORD:+-a "$REDIS_PASSWORD"} --no-auth-warning -n 1 "$@"; }
  r --scan --pattern "redbeat:sc4snmp;*" | while read -r k; do
    if [ "$(r HEXISTS "$k" definition)" = 0 ]; then
      r DEL "$k" >/dev/null; r ZREM redbeat::schedule "$k" >/dev/null; echo "deleted: $k"
    fi
  done'
```

## MongoDB

```bash
# MicroK8s: replica set member health (replication mode)
$K exec $RELEASE-mongodb-0 -c mongodb -- sh -c 'mongosh --quiet \
  ${MONGO_INITDB_ROOT_USERNAME:+-u "$MONGO_INITDB_ROOT_USERNAME" -p "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin} \
  --eval "rs.status().members.forEach(m => print(m.name + \" \" + m.stateStr + \" health=\" + m.health))"'
# Inventory records stored by SC4SNMP
$K exec $RELEASE-mongodb-0 -c mongodb -- sh -c 'mongosh --quiet \
  ${MONGO_INITDB_ROOT_USERNAME:+-u "$MONGO_INITDB_ROOT_USERNAME" -p "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin} \
  sc4snmp --eval "db.inventory.countDocuments({})"'
$K logs job/$RELEASE-mongodb-init-rs
```

```bash
# Docker Compose
sudo docker inspect mongo --format 'status={{.State.Status}} exit={{.State.ExitCode}} oom={{.State.OOMKilled}}'
sudo docker logs --tail=200 mongo
uname -r
```

**Expected:**
- In replication mode, exactly one member is `PRIMARY`, and every member reports `health=1`.
- The inventory count matches the number of devices.
- MongoDB stays `running`.

Write procedures (password rotation, replica set recovery, feature compatibility version) are in the [MongoDB configuration](https://splunk.github.io/splunk-connect-for-snmp/main/microk8s/configuration/mongo-configuration/) docs. Follow them exactly.

## MIB server

```bash
# MicroK8s
$K logs deploy/$RELEASE-mibserver --tail=300
$K rollout restart deployment $RELEASE-mibserver     # changes the deployment: recompiles local MIBs
```

```bash
# Docker Compose
sudo docker logs --tail=300 snmp-mibserver
sudo docker compose restart snmp-mibserver
```

Check whether a MIB is in the public repository: `curl -s https://pysnmp.github.io/mibs/index.csv | grep -i '<MIB-NAME>'`.

**Expected:** the logs list the compiled local MIBs and contain no `No local mibs. Skipping...` or `Illegal character` lines.

## DNS and network

```bash
# MicroK8s
microk8s kubectl get pods -n kube-system | grep -i coredns
microk8s kubectl run dnsutils --rm -it --restart=Never -n $NS \
  --image=registry.k8s.io/e2e-test-images/jessie-dnsutils:1.3 -- \
  sh -c "nslookup $RELEASE-redis.$NS; nslookup <hec-host>"
microk8s kubectl -n kube-system get configmap coredns -o yaml
microk8s kubectl describe daemonset/calico-node -n kube-system | grep -i -E 'CALICO_IPV(4|6)POOL_CIDR'
microk8s kubectl get ipaddresspool -n metallb-system -o yaml
```

```bash
# Docker Compose
sudo docker network inspect sc4snmp_network
sudo docker exec docker_compose-worker-sender-1 python3 -c "import socket; print(socket.getaddrinfo('<hec-host>', 8088))"
```

**Expected:** both names resolve. In dual-stack setups, the IPv4 and IPv6 pools are both present.

- `no route to host` or a timeout on the internal name means pod-to-DNS traffic is blocked.
- Failure on the external name only means the upstream resolvers are wrong.

## Deep debug

Use these only when logs at `DEBUG` do not explain the behavior, and turn them off afterwards.

- **pysnmp protocol debug:** top-level `pysnmpDebug: "dsp,msgproc,io"` in `values.yaml`, or `PYSNMP_DEBUG=dsp,msgproc,io` in `.env`. Other flags: `secmod` for SNMPv3 security, `mibbuild`, `mibview`, `app`, `all`.
- **Flower (Celery task UI):** `flower.enabled: true`, with `flower.loadBalancerIP` set when needed. On Compose, `sudo docker compose --profile debug up -d`; the port is `FLOWER_PORT`.

## Documentation

| Topic | Page |
|---|---|
| Polling and walk errors | https://splunk.github.io/splunk-connect-for-snmp/main/troubleshooting/polling-issues/ |
| Trap errors | https://splunk.github.io/splunk-connect-for-snmp/main/troubleshooting/traps-issues/ |
| Discovery errors | https://splunk.github.io/splunk-connect-for-snmp/main/troubleshooting/discovery-issues/ |
| MongoDB, upgrade, and metric naming issues | https://splunk.github.io/splunk-connect-for-snmp/main/troubleshooting/general-issues/ |
| Logs, log level, and Splunk searches | https://splunk.github.io/splunk-connect-for-snmp/main/troubleshooting/configuring-logs/ |
| kubectl and docker commands | https://splunk.github.io/splunk-connect-for-snmp/main/troubleshooting/k8s-commands/ and https://splunk.github.io/splunk-connect-for-snmp/main/troubleshooting/docker-commands/ |
| `values.yaml` parameters | https://splunk.github.io/splunk-connect-for-snmp/main/microk8s/configuration/values-params-description/ |
| `.env` variables | https://splunk.github.io/splunk-connect-for-snmp/main/dockercompose/6-env-file-configuration/ |
| Monitoring dashboard | https://splunk.github.io/splunk-connect-for-snmp/main/dashboard/ |
| Architecture | https://splunk.github.io/splunk-connect-for-snmp/main/architecture/design/ |
| Releases and changelog | https://github.com/splunk/splunk-connect-for-snmp/releases |
