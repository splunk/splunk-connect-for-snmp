import logging
import time

from pysnmp.hlapi import *

from test.splunk_test_utils import splunk_single_search

logger = logging.getLogger(__name__)


def send_trap(host, port, object_identity, *var_binds):
    iterator = sendNotification(
        SnmpEngine(),
        CommunityData("public", mpModel=0),
        UdpTransportTarget((host, port)),
        ContextData(),
        "trap",
        NotificationType(ObjectIdentity(object_identity))
        .addVarBinds(*var_binds)
        .loadMibs("SNMPv2-MIB"),
    )

    error_indication, error_status, error_index, var_binds = next(iterator)

    if error_indication:
        logger.error(f"{error_indication}")


def test_integration(request, setup_splunk):
    trap_external_ip = request.config.getoption("trap_external_ip")
    logger.info(f"I have: {trap_external_ip}")

    time.sleep(2)
    # send trap
    varbind1 = ("1.3.6.1.6.3.1.1.4.3.0", "1.3.6.1.4.1.20408.4.1.1.2")
    varbind2 = ("1.3.6.1.2.1.1.1.0", OctetString("my system"))
    send_trap(trap_external_ip, 162, "1.3.6.1.6.3.1.1.5.2", varbind1, varbind2)

    # wait for the message to be processed
    time.sleep(2)

    search_query = """search index="snmp" sourcetype="sc4snmp:traps"
                     "SNMPv2-MIB::sysUpTime.0=0" "SNMPv2-MIB::snmpTrapOID.0=SNMPv2-MIB::warmStart" 
                     "SNMP-COMMUNITY-MIB::snmpTrapAddress.0=0.0.0.0" 
                     "SNMP-COMMUNITY-MIB::snmpTrapCommunity.0=public" 
                     "SNMPv2-MIB::snmpTrapEnterprise.0=SNMPv2-SMI::enterprises.20408.4.1.1.2"
                     | head 1"""

    result_count, events_count = splunk_single_search(setup_splunk, search_query)

    assert result_count == 1
