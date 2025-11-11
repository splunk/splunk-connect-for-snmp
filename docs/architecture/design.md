# Architecture

SC4SNMP is deployed using a Kubernetes distribution, typically MicroK8s,
that is designed to be a low-touch experience for integration with sensitive
edge network devices. It will typically be deployed in the same network
management zone as the monitored devices and separated from Splunk by an
existing firewall.

![image](../images/sc4snmp_deployment.png)


## High-level Design 

SC4SNMP has two main purposes. The first one is used to collect SNMP data from network 
devices according to planned schedules and the second one is responsible for listening to SNMP traps.

![image](../images/sc4snmp_architecture.png)

Diagram above present high level architecture of Splunk Connector for SNMP, it contains following components:

- **UI** - user interface for configuring the SC4SNMP profiles, groups, and inventory. It is applying changes to 
  SC4SNMP by creating the inventory job.
- **Poller** - responsible for getting selected data from SNMP agents in set periods of time. Celery is used for 
  planning the schedules and executing the incoming tasks, signaled from Redis as message broker.
- **Trap** - responsible for listening and receiving trap notifications from SNMP agents. The listener is always 
  waiting for the messages coming on the specified port and passing them to the trap worker for further 
  processing.
- **Discovery** - responsible for detecting SNMP-enabled devices within a given subnet. Celery is used to schedule and execute the discovery tasks, with Redis acting as the message broker.
- **MIB Server** - responsible for serving MIBs to SNMP Workers and translating oids to varbinds.
- **MongoDB** - used for storing configuration and state of the SC4SNMP.
- **Inventory** - job used for updating the information about SC4SNMP configuration. It is run after every update to 
  the `values.yaml` file if polling is enabled.
- **Sender** - responsible for sending data received from poller or trap workers to the Splunk HEC or OTel (SignalFx).

