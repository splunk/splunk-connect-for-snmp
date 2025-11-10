from pysnmp.carrier.asyncio.dgram import udp, udp6
from pysnmp.entity import config, engine
from pysnmp.entity.rfc3413 import cmdrsp, context
from pysnmp.hlapi.v3arch.asyncio import SnmpEngine


import asyncio


# Set the port to 1611 instead of 161, because 161 is a
# privileged port and requires root access
AGENT_PORT = 1611


async def start_agent(
    enable_ipv6: bool = False,
) -> SnmpEngine:
    snmpEngine = engine.SnmpEngine()

    config.add_transport(
        snmpEngine,
        udp.DOMAIN_NAME,
        udp.UdpTransport().open_server_mode(("localhost", AGENT_PORT)),
    )

    if enable_ipv6:
        config.add_transport(
            snmpEngine,
            udp6.DOMAIN_NAME,
            udp6.Udp6Transport().open_server_mode(("localhost", AGENT_PORT)),
        )

    config.add_v1_system(snmpEngine, "public", "public")

    # Allow read MIB access for this user / securityModels at VACM
    config.add_vacm_user(snmpEngine, 2, "public", "noAuthNoPriv", (1, 3, 6), (1, 3, 6))

    # Configure SNMP context
    snmpContext = context.SnmpContext(snmpEngine)
    cmdrsp.GetCommandResponder(snmpEngine, snmpContext)
    cmdrsp.NextCommandResponder(snmpEngine, snmpContext)
    cmdrsp.BulkCommandResponder(snmpEngine, snmpContext)
    cmdrsp.SetCommandResponder(snmpEngine, snmpContext)

    snmpEngine.transport_dispatcher.job_started(1)

    snmpEngine.open_dispatcher()

    await asyncio.sleep(1)

    return snmpEngine


class AgentContextManager:
    """
    A context manager for managing the lifecycle of an SNMP test agent.

    Usage:
    async with AgentContextManager() as agent:
        # Perform operations with the agent

    When the context is entered, the agent is started using the `start_agent()` function.
    When the context is exited, the agent's transport dispatcher is stopped and closed.
    """

    def __init__(
        self,
        enable_ipv6: bool = False,
        enable_custom_objects: bool = False,
        enable_table_creation: bool = False,
    ):
        self.enable_ipv6 = enable_ipv6
        self.enable_custom_objects = enable_custom_objects
        self.enable_table_creation = enable_table_creation

    async def __aenter__(self):
        self.agent = await start_agent(
            self.enable_ipv6
        )
        return self.agent

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.agent.transport_dispatcher.job_finished(1)
        self.agent.close_dispatcher()
