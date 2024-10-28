# Lightweight SC4SNMP installation

SC4SNMP can be successfully installed in small environments with 2 CPUs and 4 GB of memory.
However, Splunk OpenTelemetry Collector for Kubernetes cannot be installed in a small
environment along with SC4SNMP. Additionally, the `resources` limits must be set for Kubernetes
pods or Docker containers. See the example of `values.yaml` with the appropriate resources [here][lightweight_doc_link].

For the rest of installation process you can follow the instructions from **Getting started** section with the deployment of your choice.

Keep in mind that a lightweight instance of SC4SNMP will not be able to poll from many devices and may experience delays 
if there is frequent polling.

[lightweight_doc_link]: https://github.com/splunk/splunk-connect-for-snmp/blob/main/examples/lightweight_installation.yaml
