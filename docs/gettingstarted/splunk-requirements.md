# Splunk requirements

## Prepare Splunk

### Requirements (Splunk Enterprise/Enterprise Cloud)

1. Complete the installation of [Splunk IT Essentials Work](https://docs.splunk.com/Documentation/ITE/latest/Work/Overview) OR [Splunk IT Service Intelligence](https://docs.splunk.com/Documentation/ITSI/4.9.2/Install/About)
2. Verify the creation of the following indexes:
    * em_metrics (metrics type)
    * em_logs (event type)
    * netmetrics (metrics type)
    * netops (event type)
3. Create or obtain a new Splunk HTTP Event Collector token and the correct HTTPS endpoint.
4. Verify the token using [curl](https://docs.splunk.com/Documentation/Splunk/8.1.3/Data/FormateventsforHTTPEventCollector) Note: The endpoint must use a publicly trusted certificate authority.
5. The SHARED IP address to be used for SNMP Traps. Note Simple and POC deployments will use the same IP as the host server. If HA deployment will be used, the IP must be in addition to the management interface of each cluster member.
6. Obtain the IP address of an internal DNS server that can resolve the Splunk Endpoint.

### Requirements (Splunk Infrastructure Monitoring)

Obtain the following from your Splunk Observability Cloud environment:

1. Realm
2. Token