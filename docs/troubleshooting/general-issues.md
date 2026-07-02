## General issues

### MongoDB 8.x crash on Linux kernel 6.19+ (exit 139 / SIGSEGV)

The `mongo:8.0.5+` and `mongo:8.2.x` images (the default since SC4SNMP `1.16.0`) bake a `GLIBC_TUNABLES=glibc.pthread.rseq=0` setting into the image. On host kernels >= 6.19, which overhauled the RSEQ subsystem, this setting causes MongoDB's `tcmalloc` allocator to crash. The `mongo` container logs `mongod startup complete`, runs for about 30 seconds, then exits with code `139` (SIGSEGV). `OOMKilled=false`, and the next start logs `Detected unclean shutdown - Lock file is not empty`.

#### How to confirm

Check the host kernel version:

/// tab | docker compose
```bash
uname -r
```
///

/// tab | microk8s
```bash
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.nodeInfo.kernelVersion}{"\n"}{end}'
```
///

Anything `>= 6.19` is at risk. Also check container exit state:

```bash
docker inspect mongo --format 'status={{.State.Status}} exit={{.State.ExitCode}} oom={{.State.OOMKilled}}'
```

The combination `exit=139 oom=false` together with `mongod startup complete` in the container logs ~30s before the exit is the diagnostic signature.

#### Fix

SC4SNMP from version **1.17.0** ships a default `GLIBC_TUNABLES=glibc.pthread.rseq=1` on the mongo container, which restores the upstream glibc default and prevents the crash. The setting is a safe no-op on kernels < 6.19, so it is enabled unconditionally. You normally do not need to do anything.

If you previously customized the mongo container and removed/overrode the env variable, restore it:

/// tab | docker compose
In `docker_compose/.env`, ensure:

```
MONGO_GLIBC_TUNABLES=glibc.pthread.rseq=1
```

The `mongo` service in `docker-compose.yaml` already references this variable.
///

/// tab | microk8s
In `values.yaml`, ensure the entry is present (it is the default):

```yaml
mongodb:
  extraEnv:
    - name: GLIBC_TUNABLES
      value: "glibc.pthread.rseq=1"
```
///

### Upgrading SC4SNMP from 1.12.2 to 1.12.3

!!! warning "Microk8s only"

When upgrading SC4SNMP from version `1.12.2` to `1.12.3`, the subchart version of MongoDB will be updated from `13.18.5` to `15.6.26`. This upgrade requires an increase in the MongoDB `Feature Compatibility Version (FCV)` from `5.0` to `6.0`.

To facilitate this change, a new pre-upgrade job has been introduced in SC4SNMP: `mongo-fcv-upgrade-to-6`. This job automatically updates the Feature Compatibility Version on MongoDB before the installation of MongoDB version `15.6.26`.

#### Pre-Upgrade Job: `mongo-fcv-upgrade-to-6`

- The `mongo-fcv-upgrade-to-6` job is designed to ensure compatibility by running the FCV update prior to upgrading MongoDB.

#### Handling Job Failures

If the `mongo-fcv-upgrade-to-6` job fails for any reason, there are two recovery options:

1. **Reinstall SC4SNMP**:

    [Reinstall SC4SNMP](../microk8s/sc4snmp-installation.md#restart-splunk-connect-for-snmp) with **Persistent Volume Claim (PVC) deletion**.

2. **Manually Update MongoDB**:

    [Update MongoDB's Feature Compatibility Version](https://www.mongodb.com/docs/manual/release-notes/6.0-upgrade-standalone/#upgrade-procedure) manually by executing the following command:
     ```bash
     microk8s kubectl exec -it pod/<mongodb-pod-id> -n sc4snmp -- mongosh
     db.adminCommand( { setFeatureCompatibilityVersion: "6.0" })
     ```

    Replace `<mongodb-pod-id>` with the actual Pod ID of your MongoDB instance.

### Addressing Metric Naming Conflicts for Splunk Integration

When collecting SNMP metrics using SC4SNMP, metric names often contain hyphens (e.g., IF-MIB) because the default MIB format includes hyphens in Object Identifiers (OIDs) as specified by standard MIB naming conventions. 
While this naming convention is standard for SNMP MIBs, it can lead to compatibility issues when forwarding these metrics, particularly when integrating with Splunk via the OpenTelemetry (OTel) Collector's Splunk HEC metric endpoint.

The Splunk metric schema, as detailed in the [official Splunk documentation](https://help.splunk.com/en/splunk-enterprise/get-data-in/metrics/9.4/introduction-to-metrics/overview-of-metrics), generally expects metric names to adhere to 
a specific format that may not accommodate hyphens in certain contexts. Although direct ingestion into Splunk might work, 
using the [OpenTelemetry Collector Splunk HEC receiver](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/receiver/splunkhecreceiver) can expose these naming conflicts, potentially preventing successful 
data ingestion or proper metric indexing.

To ensure seamless compatibility and avoid potential issues, SC4SNMP provides a configuration option to automatically convert 
hyphens in metric names to underscores.


You can enable this conversion depending on your deployment:

/// tab | microk8s
Set `splunkMetricNameHyphenToUnderscore` to `true` within the `poller` section of `values.yaml`:

```yaml
poller:
  splunkMetricNameHyphenToUnderscore: true
```
///

/// tab | docker compose
Set `SPLUNK_METRIC_NAME_HYPHEN_TO_UNDERSCORE=true` in `.env`:

```
SPLUNK_METRIC_NAME_HYPHEN_TO_UNDERSCORE=true
```
///

Enabling this option transforms metric names from their hyphenated format to an underscore-separated format, aligning them with common Splunk metric naming conventions.

Before conversion (hyphens):

```json
{
  "frequency": "60",
  "ifAdminStatus": "up",
  "ifAlias": "1",
  "ifDescr": "GigabitEthernet1",
  "ifIndex": "1",
  "ifName": "Gi1",
  "ifOperStatus": "up",
  "ifPhysAddress": "0a:aa:ef:53:67:15",
  "ifType": "ethernetCsmacd",
  "metric_name:sc4snmp.IF-MIB.ifInDiscards": 0,
  "metric_name:sc4snmp.IF-MIB.ifInErrors": 0,
  "metric_name:sc4snmp.IF-MIB.ifInOctets": 1481605109,
  "metric_name:sc4snmp.IF-MIB.ifOutDiscards": 0,
  "metric_name:sc4snmp.IF-MIB.ifOutErrors": 0,
  "metric_name:sc4snmp.IF-MIB.ifOutOctets": 3942570709,
  "profiles": "TEST"
}
```

After conversion (underscores):

```json
{
  "frequency": "60",
  "ifAdminStatus": "up",
  "ifAlias": "1",
  "ifDescr": "GigabitEthernet1",
  "ifIndex": "1",
  "ifName": "Gi1",
  "ifOperStatus": "up",
  "ifPhysAddress": "0a:aa:ef:53:67:15",
  "ifType": "ethernetCsmacd",
  "metric_name:sc4snmp.IF_MIB.ifInDiscards": 0,
  "metric_name:sc4snmp.IF_MIB.ifInErrors": 0,
  "metric_name:sc4snmp.IF_MIB.ifInOctets": 1481605109,
  "metric_name:sc4snmp.IF_MIB.ifOutDiscards": 0,
  "metric_name:sc4snmp.IF_MIB.ifOutErrors": 0,
  "metric_name:sc4snmp.IF_MIB.ifOutOctets": 3942570709,
  "profiles": "TEST"
}
```