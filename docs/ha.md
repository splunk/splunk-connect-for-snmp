## High Availability Considerations

The SNMP protocol uses UDP as the transport protocol. Network reliability is a constraint.
Consider network architecture when designing for high availability:

* When using a single node collector, ensure automatic recovery from virtual infrastructure (i.e. VMware, Openstack, etc).
* When using a multi-node cluster, ensure nodes are not located such that a simple majority of nodes can
be lost. For example, consider row, rack, network, power, and storage.
* When determining the placement of clusters, the closest location by the number of network hops should be utilized.
* For "data center" applications, collection should be local to the data center.
* Consider IP Anycast.
