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
from integration_tests.splunk_test_utils import splunk_single_search

from pysnmp.hlapi import *

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

    search_query = """search index="em_events" sourcetype="sc4snmp:traps" earliest=-1m
                     | head 1"""

    result_count, events_count = splunk_single_search(setup_splunk, search_query)

    assert result_count == 1
