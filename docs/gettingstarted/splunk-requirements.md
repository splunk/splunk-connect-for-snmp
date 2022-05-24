# Splunk requirements

## Prepare Splunk

### Requirements (Splunk Enterprise/Enterprise Cloud)

1. Manually create the following indexes in Splunk:
   
   * Indexes for logs and metrics from SC4SNMP Connector:
       * em_metrics (metrics type)
       * em_logs (event type)
   * Indexes where SNMP Data will be forwarded:
       * netmetrics (metrics type)
       * netops (event type)
   
Note: `netmetrics` and `netops` are the default names of SC4SNMP indexes. You can use the index names of your choice and
reference it in `values.yaml` file later on.
Parameters and the instruction on how to do it is here: [SC4SNMP Parameters](sc4snmp-installation.md#configure-splunk-enterprise-or-splunk-cloud-connection)


3. Create or obtain a new Splunk HTTP Event Collector token and the correct HTTPS endpoint.
4. Verify the token using [curl](https://docs.splunk.com/Documentation/Splunk/8.1.3/Data/FormateventsforHTTPEventCollector) Note: The endpoint must use a publicly trusted certificate authority.
5. The SHARED IP address to be used for SNMP Traps. Note Simple and POC deployments will use the same IP as the host server. If HA deployment will be used, the IP must be in addition to the management interface of each cluster member.
6. Obtain the IP address of an internal DNS server that can resolve the Splunk Endpoint.

### Requirements (Splunk Infrastructure Monitoring)

Obtain the following from your Splunk Observability Cloud environment:

1. Realm
2. Token
