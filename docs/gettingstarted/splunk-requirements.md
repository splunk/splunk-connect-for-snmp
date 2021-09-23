# Splunk requirements

## Prepare Splunk

### Requirements (Splunk Enterprise/Enterprise Cloud)

1. Complete the installation of [Splunk IT Essentials Work](https://docs.splunk.com/Documentation/ITE/latest/Work/Overview) OR [Splunk IT Service Intelligence](https://docs.splunk.com/Documentation/ITSI/4.9.2/Install/About)
2. Verify the creation of the following indexes
    * em_metrics (metrics type)
    * em_meta (event type)
    * em_logs (event type)
3. Create or obtain a new Splunk HTTP Event Collector token and the correct https endpoint.
4. Verify the token using [curl](https://docs.splunk.com/Documentation/Splunk/8.1.3/Data/FormateventsforHTTPEventCollector) Note: The endpoint must use a publicly trusted certificate authority.
5. The SHARED IP address to be used for SNMP Traps. Note Simple and POC deployments will use the same IP as the host server if HA deployment will be used the IP must be in addition to the managment inteface of each cluster member.
6. Obtain the ip address of an internal DNS server able to resolve the Splunk Endpoint

### Requirements (Splunk Infrastructure Monitoring)

Obtain the correct realm and token.