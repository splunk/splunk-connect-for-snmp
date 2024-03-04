# High Availability 

The SNMP protocol uses UDP as the transport protocol. Network reliability is a constraint.
Consider network architecture when designing for high availability:

* When using a single node collector, ensure automatic recovery from virtual infrastructure, such as VMware or Openstack.
* When using a multi-node cluster, ensure nodes are not located in a way where the majority of nodes can be lost. For example, consider row, rack, network, power, and storage.
* When determining the placement of clusters, the closest location by the number of network hops should be used.
* For "data center" applications, collection should be local to the data center.
* Consider using IP Anycast.
