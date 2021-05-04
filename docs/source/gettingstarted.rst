... Getting Started

Getting Started
===================================================

Requirements (Splunk Enterprise/Enterprise Cloud)
---------------------------------------------------

1. Splunk hec token with no index restriction **or** Splunk hec token with access to _internal, netops and net_metrics

    1.1 Poller-specific indexes: we need an **event type** index called **snmp**, and **metrics type** index called **snmp_metric**
2. Known Splunk URL with trusted certificate (must be trusted by standard red hat trusted chain)
3. Physical or virtual linux host (Prefer Ubuntu or RHEL 8.1) RHEL hosts must have snap support enabled see https://snapcraft.io/docs/installing-snapd
4. One IP allocation in addition to the ip allocated to the host.
    \*Note: In the future clustering (scale out) will use this IP as a shared resource

Setup MicroK8s on Ubuntu
---------------------------------------------------

The following setup instructions are validated for release 1.20x but are subject to change.

1. Install MicroK8s
::

    sudo snap install microk8s --classic
    sudo usermod -a -G microk8s "$USER"
    sudo chown -f -R "$USER" ~/.kube
    su - "$USER"

2. Check completion status ``microk8s.status --wait-ready``
3. Install optional modules ``microk8s.enable dns:<privatedns_ip> metallb helm3``

Setup MicroK8s on CentOS
---------------------------------------------------

The following setup instructions are validated for release 1.20x but are subject to change.

1. Install MicroK8s
::

    sudo yum -y install epel-release
    sudo yum -y install snapd
    sudo systemctl enable snapd
    sudo systemctl start snapd
    sudo ln -s /var/lib/snapd/snap /snap
    sudo snap install microk8s --classic
    sudo usermod -a -G microk8s "$USER"
    sudo chown -f -R "$USER" ~/.kube
    su - "$USER"

2. Check completion status ``microk8s.status --wait-ready``
3. Install optional modules ``microk8s.enable dns:<privatedns_ip> metallb helm3``

Monitor MicroK8s
---------------------------------------------------

Note HEC TLS is required for SCK

* Install the following app on the designated search head https://splunkbase.splunk.com/app/4217/ (version 2.23 or newer) \*NOTE Do not complete the add data process for k8s
* Install the following app on the designated search head  and indexers https://splunkbase.splunk.com/app/3975/ (version 2.23 or newer)
* Create the additional index em_logs
* Get the code

.. code-block:: bash

   git clone https://github.com/splunk/splunk-connect-for-snmp.git
   cd splunk-connect-for-snmp

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

   microk8s.kubectl create secret generic remote-splunk \
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

    for f in deploy/sc4snmp/*.yaml ; do cat $f | sed 's/loadBalancerIP: replace-me/loadBalancerIP: 10.0.101.22/' | microk8s.kubectl apply -f - ; done

* Confirm deployment using ``microk8s.kubectl get pods``

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

    microk8s.kubectl apply -f deploy/sc4snmp/

* Confirm deployment using ``microk8s.kubectl get pods``

.. code-block:: bash

    NAME                                  READY   STATUS    RESTARTS   AGE
    mib-server-75c64468d4-nxfhw           1/1     Running   0          1m
    mongo-65484dd8b4-49dfj                1/1     Running   0          1m
    rabbitmq-65bc7457dd-xzdq7             1/1     Running   0          1m
    sc4-snmp-scheduler-5c9f69784d-pfmgq   1/1     Running   0          1m
    sc4-snmp-worker-5dff6b8c49-q7n2t      1/1     Running   0          1m

* Test the poller by logging to Splunk and confirm presence of events in snmp index and metrics in snmp_metric index.

* You can change the inventory contents in scheduler-config.yaml and use following command to apply the changes to Kubernetes cluster. Agents configuration is placed in scheduler-config.yaml under section inventory.csv, content below is interpreted as csv file with following columns:

1. host (IP or name)
2. version of SNMP protocol
3. community string authorisation phrase
4. profile of device (varBinds of profiles can be found in convig.yaml section of scheduler-config.yaml file)
5. frequency in seconds (how often SNMP connector should ask agent for data)


.. code-block:: bash

    microk8s.kubectl apply -f deploy/sc4snmp/scheduler-config.yaml