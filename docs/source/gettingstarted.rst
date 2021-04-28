.. Getting Started

###################################################
Getting Started
###################################################


**************************************************
Prepare Splunk
**************************************************


Requirements (Splunk Enterprise/Enterprise Cloud)
===================================================


1. Complete the installation of 
    1.1 `Splunk app for Infrastructure <https://docs.splunk.com/Documentation/InfraApp/latest/Install/About>`_ (Splunk Enterprise Customers)
    1.2 `Splunk IT Essentials Work <https://docs.splunk.com/Documentation/ITE/latest/Work/Overview>`_ (Splunk Enterprise Cloud Customers)
2. Verify the creation of the following indexes
    1.1 em_metrics (metrics type)
    1.2 em_meta (event type)
    1.3 em_logs (event type)
3. Create or obtain a new Splunk HTTP Event Collector token and the correct https endpoint.
4. Verify the token using `curl <https://docs.splunk.com/Documentation/Splunk/8.1.3/Data/FormateventsforHTTPEventCollector>`_ Note: The endpoint must use a publicly trusted certificate authority.
5. The SHARED IP address to be used for SNMP Traps. Note Simple and POC deployments will use the same IP as the host server if HA deployment will be used the IP must be in addition to the managment inteface of each cluster memember.
6. Obtain the ip address of an internal DNS server able to resolve the Splunk Endpoint
7. The "snap" command for your operating system


Requirements (Splunk Infrastructure Monitoring)
===================================================

Obtain the correct realm and token.

**************************************************
Deploy
**************************************************

Get current deployment scripts
===================================================

.. code-block:: bash

   git clone https://github.com/splunk/splunk-connect-for-snmp.git
   cd splunk-connect-for-snmp



Deploy SC4SNMP Interactive
===================================================

.. code-block:: bash

    ./deploy/deploy.sh 


Deploy SC4SNMP non-interactive
===================================================

.. code-block:: bash

    MODE=splunk \
    PROTO=https \
    INSECURE_SSL=true \
    HOST=i-08c221389a3b9899a.ec2.splunkit.io \
    PORT=8088 \
    TOKEN=450a69af-16a9-4f87-9628-c26f04ad3785 \
    METRICS_INDEX=em_metrics \
    EVENTS_INDEX=em_events \
    META_INDEX=em_logs \
    CLUSTER_NAME=foo \
    SHAREDIP=10.0.0.1/32 \
    RESOLVERIP=8.8.4.4 \
    ./deploy/deploy.sh 


* Confirm deployment using ``kubectl get svc -n sc4snmp`` confirm the value of external-ip in the row below matches IP used above

.. code-block:: bash

    NAME                 TYPE           CLUSTER-IP       EXTERNAL-IP    PORT(S)             AGE
    sc4-snmp-traps       LoadBalancer   10.152.183.134   10.202.6.253   162:32652/UDP       28h

Test Monioring with SCK (Requires Splunk)
===================================================

Confirm the following search returns results ``| mcatalog values(metric_name)  where index=em_metrics AND metric_name=kube* AND host=<hostname>``


Test SNMP Traps
===================================================

* Test the trap from a linux system with snmp installed replace the ip ``10.0.101.22`` with the shared ip above

.. code-block:: bash
    apt-get install snmpd
    snmptrap -v2c -c public 10.0.101.22 123 1.3.6.1.6.3.1.1.5.1 1.3.6.1.2.1.1.5.0 s test

* Search splunk, one event per trap command with the host value of the test machine ip will be found

.. code-block:: bash
    index=* sourcetype="sc4snmp:traps"


Setup Poller
===================================================

* Test the poller by logging to Splunk and confirm presence of events in snmp em_logs and metrics in em_metrics index.

* You can change the inventory contents in scheduler-config.yaml and use following command to apply the changes to Kubernetes cluster.
Agents configuration is placed in scheduler-config.yaml under section inventory.csv, content below is interpreted as csv file
with following columns:

*. host (IP or name)
*. version of SNMP protocol
*. community string authorisation phrase
*. profile of device (varBinds of profiles can be found in convig.yaml section of scheduler-config.yaml file)
*. frequency in seconds (how often SNMP connector should ask agent for data)

.. code-block:: bash
    cp deploy/sc4snmp/ftr/scheduler-inventory.yaml ~/scheduler-inventory.yaml
    vi ~/scheduler-inventory.yaml
    # Remove the comment from line 2 and correct the ip and community value
    kubectl apply -n sc4snmp -f ~/scheduler-inventory.yaml


Test Poller
===================================================

Search splunk, one event per trap command with the host value of the test machine ip will be found

.. code-block:: bash

    index=* sourcetype="sc4snmp:meta" SNMPv2_MIB__sysLocation_0="*" | dedup host

.. code-block:: bash

    | mcatalog values(metric_name)  where index=em_metrics AND metric_name=sc4snmp* AND host=<hostname>

Maintain
===================================================

Manage configuration obtain and update communities, user/secrets and inventories
