# Autodiscovery integration environment

The autodiscovery integration test uses six lightweight SNMP agents split
between two variations: three v2c agents and three v3 SHA/AES agents.

| Deployment | Discovery key | Scanned subnet | Agent IPs | SNMP |
| --- | --- | --- | --- | --- |
| MicroK8s | `integration_v2c` | `10.1.1.0/29` | `10.1.1.1`-`10.1.1.3` | v2c, community `public` |
| MicroK8s | `integration_v3` | `10.2.2.0/29` | `10.2.2.1`-`10.2.2.3` | v3, SHA/AES |
| Docker Compose | `integration_v2c` | `10.4.4.0/29` | `10.4.4.1`-`10.4.4.3` | v2c, community `public` |
| Docker Compose | `integration_v3` | `10.5.5.0/29` | `10.5.5.1`-`10.5.5.3` | v3, SHA/AES |

A `/29` contains six usable host addresses, so each discovery task checks only
six candidates instead of scanning an entire `/24`. MicroK8s creates every
simulator as a static-IP Pod. Docker Compose SC4SNMP uses a separate simulator
namespace and IP ranges, but the simulators are deployed through the same
MicroK8s method.

The agent names are `snmp-agent-v1-001` through `snmp-agent-v1-003` and
`snmp-agent-v2-001` through `snmp-agent-v2-003`. Setup verifies each requested
IP against the Pod's reported `status.podIP` and prints all simulator Pods with
their IPs.

Each agent serves the SNMPv2-MIB system scalars and a minimal IF-MIB interface.
The tests require the SC4SNMP-generated CSV to exactly match all six deployed
agents and verify v2c and v3 credentials, device rules, and base OID reads.

To exercise `delete_already_discovered: true`, the test temporarily makes
`snmp-agent-v1-003` unreachable with a NetworkPolicy. It verifies that the
agent is removed from the CSV, restores connectivity, and verifies that the
complete three-address v2c set returns.
