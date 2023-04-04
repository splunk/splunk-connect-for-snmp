# Lightweight SC4SNMP installation

SC4SNMP can be successfully installed in small environments with 2 CPUs and 4 GB of memory.
One important thing to remember is that Splunk OpenTelemetry Collector for Kubernetes cannot be installed in such a small
environment along with SC4SNMP. The other difference from normal installation is that the `resources` limits must be set for Kubernetes
pods. See the example of `values.yaml` with the appropriate resources [here][lightweight_doc_link].


The rest of the installation is the same as in [online](gettingstarted/sc4snmp-installation.md), or the
[offline](offlineinstallation/offline-sc4snmp.md) installation.

Keep in mind that a lightweight instance of SC4SNMP won't be able to poll from many devices and may experience delays 
if there is frequent polling.

[lightweight_doc_link]: https://github.com/splunk/splunk-connect-for-snmp/blob/main/examples/lightweight_installation.yaml