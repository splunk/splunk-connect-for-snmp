# Prerequisites for the Splunk Connect for SNMP

See the following prerequisites for the Splunk Connect for SNMP.

### Requirements for Splunk Enterprise or Enterprise Cloud

1. Manually create the following indexes in Splunk:
   
   * Indexes to store Splunk Connect for SNMP logs and metrics: 
       * em_metrics (metrics type)
       * em_logs (event type)
   * Destination indexes for forwarding SNMP data: 
       * netmetrics (metrics type)
       * netops (event type)
   
> **_Note:_** `netmetrics` and `netops` are the default names of SC4SNMP indexes. You can use the index names of your choice and
> reference it in the `values.yaml` file later on. See [SC4SNMP Parameters](../microk8s/sc4snmp-installation.md#configure-splunk-enterprise-or-splunk-cloud-connection) for details.

2. Create or obtain a new Splunk HTTP Event Collector token and the correct HTTPS endpoint.
3. Verify the token using [curl](https://docs.splunk.com/Documentation/Splunk/8.1.3/Data/FormateventsforHTTPEventCollector). The endpoint must use a publicly trusted certificate authority.
4. Use the shared IP address for SNMP traps. Simple and POC deployments will use the same IP address as the host server. For an HA deployment, use the management interface and the IP address of each cluster member. 
5. Obtain the IP address of an internal DNS server that can resolve the Splunk Endpoint.

### Requirements for Splunk Infrastructure Monitoring

!!! warning 
    The Splunk Observability Cloud integration (sim) uses the Splunk OpenTelemetry Collector as an additional component in our pipeline. In this setup, the collector transforms metrics received via Splunk HEC into the SignalFx format for ingestion into Splunk Observability Cloud.
    Because this path is primarily a transformation layer rather than a native O11y instrumentation, the resulting metrics may not fully match Splunk Observability Cloud’s data model, naming conventions, or recommended dimensions.
    We recommend validating output carefully in a controlled environment before enabling sim.enabled: true broadly, and adjusting SNMP profiles or transformation rules to ensure consistency.

Obtain the following from your Splunk Observability Cloud environment:

1. Realm
2. Token