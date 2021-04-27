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
5. Confirm the following search returns results ``| mcatalog values(metric_name)  where index=em_metrics AND metric_name=kube* AND host=<hostname>``


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


Deploy SC4SNMP
---------------------------------------------------

* Apply the manifests, replace the ip ``10.0.101.22`` with the shared IP noted above

.. code-block:: bash

    for f in deploy/sc4snmp/*.yaml ; do cat $f | sed 's/loadBalancerIP: replace-me/loadBalancerIP: 10.0.101.22/' | microk8s.kubectl apply -f - ; done


* Confirm deployment using ``kubectl get pods``

.. code-block:: bash

    NAME                                                 READY   STATUS    RESTARTS   AGE
    mongo-65484dd8b4-fnzw4                               1/1     Running   1          28h
    sc4-snmp-traps-55bf6ff8f6-wwbnc                      1/1     Running   1          28h
    mib-server-6bdd68795c-cpvpl                          1/1     Running   1          28h
    rabbitmq-65bc7457dd-wtj4m                            1/1     Running   1          28h
    sc4-snmp-scheduler-5c6db68ff4-bnpn9                  1/1     Running   1          28h
    sc4-snmp-otel-5bb6d85555-2cwb7                       1/1     Running   1          28h
    sc4-snmp-worker-6f45794df7-qxl2m                     1/1     Running   1          28h
    
* Confirm deployment using ``kubectl get svc`` confirm the value of external-ip in the row below matches IP used above

.. code-block:: bash

    NAME                 TYPE           CLUSTER-IP       EXTERNAL-IP    PORT(S)             AGE
    sc4-snmp-traps       LoadBalancer   10.152.183.134   10.202.6.253   162:32652/UDP       28h


Test SNMP Traps
---------------------------------------------------

* Test the trap from a linux system with snmp installed replace the ip ``10.0.101.22`` with the shared ip above

.. code-block:: bash
    apt-get install snmpd
    snmptrap -v2c -c public 10.0.101.22 123 1.3.6.1.6.3.1.1.5.1 1.3.6.1.2.1.1.5.0 s test

* Search splunk, one event per trap command with the host value of the test machine ip will be found

.. code-block:: bash
    index=* sourcetype="sc4snmp:traps"


Setup Poller
---------------------------------------------------

* Test the poller by logging to Splunk and confirm presence of events in snmp em_logs and metrics in em_metrics index.

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