# Dashboard

Using dashboard you can monitor SC4SNMP and be sure that is healthy and working correctly.

## Presetup Splunk and SC4SNMP

1. [Create metrics indexes](gettingstarted/splunk-requirements.md#requirements-for-splunk-enterprise-or-enterprise-cloud) in Splunk.
2. Enable metrics logging for your runtime:
    * For K8S install [Splunk OpenTelemetry Collector for K8S](gettingstarted/sck-installation.md)
    * For docker-compose use [Splunk logging driver for docker](dockercompose/9-splunk-logging.md)

## Install dashboard

1. In Splunk platform open **Search -> Dashboards**.
2. Click on **Create New Dashboard** and make an empty dashboard. Be sure to choose Classic Dashboards.
3. In the **Edit Dashboard** view, go to Source and replace the initial xml with the contents of [dashboard/dashboard.xml](https://github.com/splunk/splunk-connect-for-snmp/blob/main/dashboard/dashboard.xml) published in the SC4S repository.
4. Saving your changes. Your dashboard is ready to use.