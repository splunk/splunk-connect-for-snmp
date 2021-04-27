... Getting Started

Prepare Splunk Enterprise
===================================================

Requirements (Splunk Enterprise/Enterprise Cloud)
---------------------------------------------------

1. Complete the installation of 
    1.1 `Splunk app for Infrastructure <https://docs.splunk.com/Documentation/InfraApp/latest/Install/About>`_ (Splunk Enterprise Customers)
    1.2 `Splunk IT Essentials Work <https://docs.splunk.com/Documentation/ITE/latest/Work/Overview>`_ (Splunk Enterprise Cloud Customers)
2. Verify the creation of the following indexes
    1.1 em_metrics (metrics type)
    1.2 em_meta (event type)
    1.3 em_logs (event type)
3. Create or obtain a new Splunk HTTP Event Collector token and the correct https endpoint.
4. Verify the token using `curl <https://docs.splunk.com/Documentation/Splunk/8.1.3/Data/FormateventsforHTTPEventCollector>`_ Note: The endpoint must use a publicly trusted certificate authority.
5. The IP address to be used for SNMP Traps. Note if HA deployment will be used the IP must be in addition to the managment inteface of each cluster memember.
6. Obtain the ip address of an internal DNS server able to resolve the Splunk Endpoint

Requirements (Splunk Enterprise/Enterprise Cloud)
---------------------------------------------------

Obtain the correct realm and token.

Setup MicroK8s
---------------------------------------------------

The following setup instructions are validated for release 1.20x but are subject to change.

1. Install MicroK8s ``sudo snap install microk8s --classic``
2. Check completion status ``sudo microk8s status --wait-ready``
3. Install optional modules ``sudo microk8s enable dns:<privatedns_ip> metallb helm3``
4. Alias kubectl ``alias kubectl="microk8s kubectl"``
4. Alias kubectl ``alias heml3="microk8s helm3"``
5. Grant access to the kubectl config file ``sudo usermod -a -G microk8s $USER``
6. Grant access to the kubectl config file ``sudo chown -f -R $USER ~/.kube``
7. Refresh credentials ``su - $USER``

Get current deployment scripts
---------------------------------------------------

.. code-block:: bash

   git clone https://github.com/splunk/splunk-connect-for-snmp.git
   cd splunk-connect-for-snmp

Monitor MicroK8s (Requires Splunk Enterprise/Cloud)
---------------------------------------------------

1. Ensure Requirements are meet above
2. Add the Helm repository ``microk8s.helm3 repo add splunk https://splunk.github.io/splunk-connect-for-kubernetes/``
3. Deploy Splunk Connect for Kubernetes ``deploy/sck/deploy_sck.sh``
4. Wait 30 seconds
5. Verify 






* Install Splunk Connect for k8s on the cluster. 

.. code-block:: bash

    pushd deploy/sck
    MONITORING_MACHINE='hec-input.fqdn.com' \
    GLOBAL_HEC_INSECURE_SSL=true \
    OBJECTS_INSECURE_SSL=true \
    METRICS_INSECURE_SSL=true \
    HEC_TOKEN='token' \
    HEC_PORT='8088' \
    CLUSTER_NAME='sc4s' \
    bash deploy_sck_mk8s.sh \
    ; popd

* Verify by navigation to to the "Splunk App for Infrastructure" app click investigate and filter for the cluster name used.

Setup Secrets
---------------------------------------------------

Execute the following commands, use the correct values for your env:

* Setup URL and token secrets (you can remove SignalFX secrets when SignalFX exporter is not configured)

.. code-block:: bash

   kubectl create secret generic remote-splunk \
   --from-literal=SPLUNK_HEC_URL=https://hec-input.fqdn.com:8088/services/collector \
   --from-literal=SPLUNK_HEC_TLS_SKIP_VERIFY=true \
   --from-literal=SPLUNK_HEC_TOKEN=splunkhectoken \
   --from-literal=SIGNALFX_TOKEN=signalfxtoken \
   --from-literal=SIGNALFX_REALM=signalfxrealm


Configure Open Telemetry Collector
---------------------------------------------------

One can find description of Splunk and SIM exporters under below links:
https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/exporter/splunkhecexporter
https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/exporter/signalfxexporter

One can find description of filter processor below:
https://github.com/open-telemetry/opentelemetry-collector/tree/main/processor/filterprocessor

OTEL configuration is placed in deploy/sc4snmp/otel-config.yaml

Setup Trap
---------------------------------------------------
* Apply the manifests, replace the ip ``10.0.101.22`` with the shared IP noted above

.. code-block:: bash

    for f in deploy/sc4snmp/*.yaml ; do cat $f | sed 's/loadBalancerIP: replace-me/loadBalancerIP: 10.0.101.22/' | kubectl apply -f - ; done

* Confirm deployment using ``kubectl get pods``

.. code-block:: bash

    NAME                          READY   STATUS    RESTARTS   AGE
    mib-server-54557f5846-rzg9q   1/1     Running   0          1m
    mib-server-54557f5846-pbt2h   1/1     Running   0          1m
    mongo-65484dd8b4-49dfj        1/1     Running   0          1m
    traps-676859cb8d-tnc7v        1/1     Running   0          1m

* Test the trap from a linux system with snmp installed replace the ip ``10.0.101.22`` with the shared ip above

.. code-block:: bash

    snmptrap -v2c -c public 10.0.101.22 123 1.3.6.1.6.3.1.1.5.1 1.3.6.1.2.1.1.5.0 s test

Setup Poller
---------------------------------------------------

* Apply the manifests

.. code-block:: bash

    kubectl apply -f deploy/sc4snmp/

* Confirm deployment using ``kubectl get pods``

.. code-block:: bash

    NAME                                  READY   STATUS    RESTARTS   AGE
    mib-server-75c64468d4-nxfhw           1/1     Running   0          1m
    mongo-65484dd8b4-49dfj                1/1     Running   0          1m
    rabbitmq-65bc7457dd-xzdq7             1/1     Running   0          1m
    sc4-snmp-scheduler-5c9f69784d-pfmgq   1/1     Running   0          1m
    sc4-snmp-worker-5dff6b8c49-q7n2t      1/1     Running   0          1m

* Test the poller by logging to Splunk and confirm presence of events in snmp index and metrics in snmp_metric index.

* You can change the inventory contents in scheduler-config.yaml and use following command to apply the changes to Kubernetes cluster.
Agents configuration is placed in scheduler-config.yaml under section inventory.csv, content below is interpreted as csv file
with following columns:

1. host (IP or name)
2. version of SNMP protocol
3. community string authorisation phrase
4. profile of device (varBinds of profiles can be found in convig.yaml section of scheduler-config.yaml file)
5. frequency in seconds (how often SNMP connector should ask agent for data)


.. code-block:: bash

    kubectl apply -f deploy/sc4snmp/scheduler-config.yaml