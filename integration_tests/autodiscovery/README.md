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
six candidates instead of scanning an entire `/24`. The MicroK8s deployment
creates static-IP simulator Pods. The Docker Compose deployment creates
static-IP simulator containers on two dedicated Docker bridge networks and
attaches only the discovery worker to those networks.

The agent names are `snmp-agent-v1-001` through `snmp-agent-v1-003` and
`snmp-agent-v2-001` through `snmp-agent-v2-003`. Setup verifies each requested
IP against the Pod or container runtime while keeping IP values out of normal
setup logs.

Each agent serves the SNMPv2-MIB system scalars and a minimal IF-MIB interface.
The tests require the SC4SNMP-generated CSV to exactly match all six deployed
agents and verify v2c and v3 credentials, device rules, and base OID reads.

CI deploys the simulator agents and discovery services only for the `part7`
matrix job. Poller and trap test jobs do not carry autodiscovery workloads.

To exercise `delete_already_discovered: true`, the test temporarily makes
`snmp-agent-v1-003` unreachable with a NetworkPolicy on MicroK8s or by stopping
the container on Docker. It verifies that the agent is removed from the CSV,
restores connectivity, and verifies that the complete three-address v2c set
returns.
