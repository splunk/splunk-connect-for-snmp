# Autodiscovery integration environment

The autodiscovery integration test uses 27 lightweight SNMP agents with three
nine-agent configurations: v2c at `10.1.1.1`-`10.1.1.9`, v3 SHA/AES at
`10.2.2.1`-`10.2.2.9`, and v3 MD5/AES at `10.3.3.1`-`10.3.3.9`.

| Discovery key | Scanned subnet | Actual agent IPs | Port | Agents | SNMP | Authentication | Engine ID |
| --- | --- | --- | ---: | ---: | --- | --- | --- |
| `integration_v2c` | `10.1.1.0/24` | `10.1.1.1`-`10.1.1.9` | 161 | 9 | v2c | community `public` | n/a |
| `integration_v3_sha` | `10.2.2.0/24` | `10.2.2.1`-`10.2.2.9` | 161 | 9 | v3 | SHA/AES | `8000000903000A3900000101` |
| `integration_v3_md5` | `10.3.3.0/24` | `10.3.3.1`-`10.3.3.9` | 161 | 9 | v3 | MD5/AES | `8000000903000A3900000102` |

The exact agent names are `snmp-agent-v1-001` through `snmp-agent-v1-009`,
`snmp-agent-v2-001` through `snmp-agent-v2-009`, and `snmp-agent-v3-001`
through `snmp-agent-v3-009`. MicroK8s creates them as static-IP Pods in the dedicated
`agent-simulator` namespace. The setup verifies every requested IP against the
Pod's reported `status.podIP` and fails immediately if an address is already in
use or Calico assigns a different address. Docker creates the same named
containers on three static bridge networks, and connects every discovery
worker to all three networks.

Each agent loads only 13 base OIDs: the seven SNMPv2-MIB system scalars plus a
minimal IF-MIB interface. Discovery resolves `SNMPv2-MIB::sysDescr.0` and reads
it with PySNMP `get_cmd`. The integration test uses that same symbolic MIB
resolution for `sysDescr.0`, `sysObjectID.0`, `sysUpTime.0`, and `sysName.0`,
then also fetches numeric `ifNumber.0`. This verifies MIB loading and prevents
the fixture from regressing to a single OID.

The simulator files contain numeric `.snmprec` records rather than ASN.1 MIB
modules. SNMPSim serves values by numeric OID; PySNMP loads the MIB modules in
the SC4SNMP/test client and resolves symbolic names before sending the request.
`SNMPv2-MIB` is part of PySNMP's core MIB set. Additional polling MIBs such as
`IF-MIB` are supplied by the SC4SNMP MIB server.

Discovery scans the actual simulator IPs directly on UDP port 161. Therefore,
the IP written by SC4SNMP to `discovery_devices.csv` is the same IP reported by
the deployed Pod or Docker container. The test reads the live simulator names
and IPs first, waits for SC4SNMP to create its CSV, and then requires an exact
27-address match overall as well as an exact match for each discovery key.

Nginx remains installed as a separate reachability check. It exposes three
localhost UDP health endpoints: port `2161` for v2c, `2162` for v3 SHA/AES, and
`2163` for v3 MD5/AES. These health proxies do not participate in discovery and
cannot replace simulator IPs in the CSV. Setup logs the Nginx configuration and
restart after all simulator Pods or containers are ready.

The discovery worker runs as UID/GID `10001`. Setup recreates
`integration_tests/discovery` with owner `10001:10001` and mode `0755` before
SC4SNMP starts. Setup does not create the discovery CSV; SC4SNMP discovery owns
creation and every update of `discovery_devices.csv`.

To exercise `delete_already_discovered: true`, the test makes
`snmp-agent-v1-009` unreachable. MicroK8s applies an in-memory NetworkPolicy,
and Docker stops the container. The deployed discovery code is rerun, and the
test verifies that `10.1.1.9` is removed from the SC4SNMP-generated CSV. It then
restores the agent, reruns discovery, and verifies the complete nine-address
v2c range again. The test never seeds or edits the CSV itself.
