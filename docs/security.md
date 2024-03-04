# Security Considerations

The SC4SNMP solution implements SNMP in a compatible mode for current and legacy network device gear.
SNMP is a protocol widely considered to be risky and requires threat mitigation at the network level.

* Do not expose SNMP endpoints to untrusted connections such as the internet or general LAN network of a typical enterprise.
* Do not allow SNMPv1 or SNMPv2 connections to cross a network zone where a man in the middle interception is possible.
* Many SNMPv3 devices rely on insecure cryptography including DES, MD5, and SHA. Do not assume that SNMPv3 devices and connections are secure by default.
* When possible use SNMPv3 with the most secure mutually supported protocol options. 
* The default IP of each node should be considered a management interface and should be protected from network
access by an untrusted device by a hardware or software firewall. When possible the IP allocated for SNMP communication should not be shared by the management interface.
