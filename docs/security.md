
# Security Considerations

The SC4SNMP solution implements SNMP in a compatible mode for current and legacy network device gear.
SNMP is a protocol widely considered to be risky and requires threat mitigation at the network level.

* Do not expose SNMP endpoints untrusted connections such as the internet or general LAN network of a typical enterprise.
* Do not allow SNMPv1 or SNMPv2 connections to cross a network zone where man in the middle interception is possible.
* Be aware many SNMPv3 devices rely on insecure cryptography including DES, MD5, and SHA. Do not presume SNMPv3 devices and connections are secure by default.
* When possible use SNMPv3 with the most secure protocol options mutually supported.