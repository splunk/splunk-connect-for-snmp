... Getting Started

Getting Started
===================================================

Requirements (Splunk Enterprise/Enterprise Cloud)
---------------------------------------------------

1. Splunk index for events "netops"
2. Splunk index for metrics "net_metrics"
3. Splunk hec token with no index restriction *OR* Splunk hec token with access to _internal, netops and net_metrics
4. Known Splunk URL with trusted certificate (must be trusted by standard red hat trusted chain)
5. Physical or virtual linux host (Prefer Ubuntu or RHEL 8.1) RHEL hosts must have snap support enabled see https://snapcraft.io/docs/installing-snapd
6. One IP allocation in addition to the ip allocated to the host. *Note: In the future clustering (scale out) will use this IP as a shared resource

Setup Micro K8s
---------------------------------------------------

The following setup instructions are validated for release 1.20x but are subject to change.

1. Install MicroK8s ``sudo snap install microk8s --classic``
2. Check completion status ``sudo microk8s status --wait-ready``
3. Install optional modules ``sudo microk8s enable dashboard dns registry metallb``
4. Alias kubectl ``alias kubectl="microk8s kubectl"``

Setup Secrets
---------------------------------------------------

Execute the following commands, use the correct values for your env:

* Setup URL and token secret

.. code-block:: bash

   kubectl create secret generic remote-splunk \
   --from-literal=SPLUNK_HEC_URL=https://fqdn:8088/services/collector \
   --from-literal=SPLUNK_HEC_TLS_VERIFY=yes \
   --from-literal=SPLUNK_HEC_TOKEN=sometoken
   

* Get the manifests

.. code-block:: bash

   git clone https://github.com/splunk/splunk-connect-for-snmp.git

* Apply the manifests, replace the ip ``10.0.101.22`` with the shared IP noted above

.. code-block:: bash

    cat splunk-connect-for-snmp/deploy/k8s/*.yaml  | sed 's/loadBalancerIP: replace-me/loadBalancerIP: 10.0.101.22/' | kubectl apply -f -

* Confirm deployment using ``kubectl get pods`` two(2) instances of mib-server and one (1) instance of traps example

.. code-block:: bash

    NAME                          READY   STATUS    RESTARTS   AGE
    mib-server-54557f5846-rzg9q   1/1     Running   0          1m
    mib-server-54557f5846-pbt2h   1/1     Running   0          1m
    traps-676859cb8d-tnc7v        1/1     Running   0          1m

* Test the trap from a linux system with snmp installed replace the ip ``10.0.101.22`` with the shared ip above

.. code-block:: bash

    snmptrap -v2c -c public 10.0.101.22 123 1.3.6.1.6.3.1.1.5.1 1.3.6.1.2.1.1.5.0 s test