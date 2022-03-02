#   ########################################################################
#   Copyright 2021 Splunk Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
#   ########################################################################
import logging
import time

from pysnmp.hlapi import *

from integration_tests.splunk_test_utils import splunk_single_search, create_v3_secrets, update_traps, \
    wait_for_pod_initialization

logger = logging.getLogger(__name__)


def send_trap(host, port, object_identity, mib_to_load, *var_binds):
    iterator = sendNotification(
        SnmpEngine(),
        CommunityData("public", mpModel=0),
        UdpTransportTarget((host, port)),
        ContextData(),
        "trap",
        NotificationType(ObjectIdentity(object_identity))
        .addVarBinds(*var_binds)
        .loadMibs(mib_to_load),
    )

    error_indication, error_status, error_index, var_binds = next(iterator)

    if error_indication:
        logger.error(f"{error_indication}")


def send_v3_trap(host, port, object_identity, mib_to_load, *var_binds):
    iterator = sendNotification(
        SnmpEngine(OctetString(hexValue='80003a8c04')),
        UsmUserData('snmp-poller', 'PASSWORD1', 'PASSWORD1', authProtocol=(1, 3, 6, 1, 6, 3, 10, 1, 1, 3), privProtocol=(1, 3, 6, 1, 6, 3, 10, 1, 2, 4)),
        UdpTransportTarget((host, port)),
        ContextData(),
        "trap",
        NotificationType(ObjectIdentity(object_identity))
        .addVarBinds(*var_binds)
        .loadMibs(mib_to_load),
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
    send_trap(trap_external_ip, 162, "1.3.6.1.6.3.1.1.5.2", "SNMPv2-MIB", varbind1, varbind2)

    # wait for the message to be processed
    time.sleep(2)

    search_query = """search index="netops" sourcetype="sc4snmp:traps" earliest=-1m
                     | head 1"""

    result_count, events_count = splunk_single_search(setup_splunk, search_query)

    assert result_count == 1


def test_added_varbind(request, setup_splunk):
    trap_external_ip = request.config.getoption("trap_external_ip")
    logger.info(f"I have: {trap_external_ip}")

    time.sleep(2)
    # send trap
    varbind1 = ('1.3.6.1.2.1.1.1.0', OctetString('test_added_varbind'))
    send_trap(trap_external_ip, 162, "1.3.6.1.2.1.2.1", "SNMPv2-MIB", varbind1)

    # wait for the message to be processed
    time.sleep(2)

    search_query = """search index="netops" "SNMPv2-MIB.sysDescr.value"="test_added_varbind" """

    result_count, events_count = splunk_single_search(setup_splunk, search_query)

    assert result_count == 1


def test_many_traps(request, setup_splunk):
    trap_external_ip = request.config.getoption("trap_external_ip")
    logger.info(f"I have: {trap_external_ip}")

    time.sleep(2)
    # send trap
    varbind1 = ('1.3.6.1.2.1.1.1.0', OctetString('test_many_traps'))
    for _ in range(5):
        send_trap(trap_external_ip, 162, "1.3.6.1.2.1.2.1", "SNMPv2-MIB", varbind1)

    # wait for the message to be processed
    time.sleep(2)

    search_query = """search index="netops" "SNMPv2-MIB.sysDescr.value"="test_many_traps" """

    result_count, events_count = splunk_single_search(setup_splunk, search_query)

    assert result_count == 5


def test_more_than_one_varbind(request, setup_splunk):
    trap_external_ip = request.config.getoption("trap_external_ip")
    logger.info(f"I have: {trap_external_ip}")

    time.sleep(2)
    # send trap
    varbind1 = ('1.3.6.1.2.1.1.4.0', OctetString('test_more_than_one_varbind_contact'))
    varbind2 = ('1.3.6.1.2.1.1.1.0', OctetString('test_more_than_one_varbind'))
    send_trap(trap_external_ip, 162, "1.3.6.1.2.1.2.1", "SNMPv2-MIB", varbind1, varbind2)

    # wait for the message to be processed
    time.sleep(2)

    search_query = """search index="netops" | search "SNMPv2-MIB.sysDescr.value"="test_more_than_one_varbind" 
    "SNMPv2-MIB.sysContact.value"=test_more_than_one_varbind_contact """

    result_count, events_count = splunk_single_search(setup_splunk, search_query)

    assert result_count == 1


def test_loading_mibs(request, setup_splunk):
    trap_external_ip = request.config.getoption("trap_external_ip")
    logger.info(f"I have: {trap_external_ip}")

    time.sleep(2)
    # send trap
    varbind1 = ('1.3.6.1.6.3.1.1.4.1.0', '1.3.6.1.4.1.15597.1.1.1.1.0.1')
    send_trap(trap_external_ip, 162, "1.3.6.1.4.1.15597.1.1.1.1", "SNMPv2-MIB", varbind1)

    # wait for the message to be processed
    time.sleep(2)

    search_query = """search index=netops "SNMPv2-MIB.snmpTrapOID.value"="AVAMAR-MCS-MIB::eventTrap"  """

    result_count, events_count = splunk_single_search(setup_splunk, search_query)

    assert result_count == 1


def test_trap_v3(request, setup_splunk):
    trap_external_ip = request.config.getoption("trap_external_ip")
    create_v3_secrets()
    update_traps(["secretv4"])
    logger.info(f"I have: {trap_external_ip}")
    time.sleep(2)
    wait_for_pod_initialization()
    # send trap
    varbind1 = ('1.3.6.1.2.1.1.4.0', OctetString('test_trap_v3'))
    send_v3_trap(trap_external_ip, 162, "1.3.6.1.2.1.1.0", "SNMPv2-MIB", varbind1)

    # wait for the message to be processed
    time.sleep(2)

    search_query = """search index=netops "SNMPv2-MIB.sysContact.value"="test_trap_v3"  """

    result_count, events_count = splunk_single_search(setup_splunk, search_query)

    assert result_count == 1