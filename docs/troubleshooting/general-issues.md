## General issues

### Upgrading SC4SNMP from 1.12.2 to 1.12.3

When upgrading SC4SNMP from version `1.12.2` to `1.12.3`, the subchart version of MongoDB will be updated from `13.18.5` to `15.6.26`. This upgrade requires an increase in the MongoDB `Feature Compatibility Version (FCV)` from `5.0` to `6.0`.

To facilitate this change, a new pre-upgrade job has been introduced in SC4SNMP: `mongo-fcv-upgrade-to-6`. This job automatically updates the Feature Compatibility Version on MongoDB before the installation of MongoDB version `15.6.26`.

#### Pre-Upgrade Job: `mongo-fcv-upgrade-to-6`

- The `mongo-fcv-upgrade-to-6` job is designed to ensure compatibility by running the FCV update prior to upgrading MongoDB.

#### Handling Job Failures

If the `mongo-fcv-upgrade-to-6` job fails for any reason, there are two recovery options:

1. **Reinstall SC4SNMP**:

    [Reinstall SC4SNMP](../../microk8s/sc4snmp-installation#restart-splunk-connect-for-snmp) with **Persistent Volume Claim (PVC) deletion**.

2. **Manually Update MongoDB**:

    [Update MongoDB's Feature Compatibility Version](https://www.mongodb.com/docs/manual/release-notes/6.0-upgrade-standalone/#upgrade-procedure) manually by executing the following command:
     ```bash
     microk8s exec -it pod/<mongodb-pod-id> -n sc4snmp mongosh
     db.adminCommand( { setFeatureCompatibilityVersion: "6.0" })
     ```

    Replace `<mongodb-pod-id>` with the actual Pod ID of your MongoDB instance.

#### Addressing Metric Naming Conflicts for Splunk Integration

When collecting SNMP metrics using SC4SNMP, the default translation of Object Identifiers (OIDs) by pysnmp often results 
in metric names containing hyphens (e.g., IF-MIB). While this format is natively understood by pysnmp, it can lead to compatibility 
issues when forwarding these metrics, particularly when integrating with Splunk via the OpenTelemetry (OTel) Collector's Splunk HEC metric endpoint.

The Splunk metric schema, as detailed in the [official Splunk documentation](https://help.splunk.com/en/splunk-enterprise/get-data-in/metrics/9.4/introduction-to-metrics/overview-of-metrics), generally expects metric names to adhere to 
a specific format that may not accommodate hyphens in certain contexts. Although direct ingestion into Splunk might work, 
using the [OpenTelemetry Collector Splunk HEC receiver](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/receiver/splunkhecreceiver) can expose these naming conflicts, potentially preventing successful 
data ingestion or proper metric indexing.

To ensure seamless compatibility and avoid potential issues, SC4SNMP provides a configuration option to automatically convert 
hyphens in metric names to underscores.


You can enable this conversion by setting the `splunkMetricNameHyphenToUnderscore` parameter to `true` within the `poller` section of your SC4SNMP configuration:

```yaml
poller:
  splunkMetricNameHyphenToUnderscore: true
```

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