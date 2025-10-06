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
import asyncio
import logging
import os
import re

import pytest
from pysnmp.hlapi.v3arch.asyncio import *

from integration_tests.splunk_test_utils import (
    create_v3_secrets_compose,
    create_v3_secrets_microk8s,
    splunk_single_search,
    update_file_microk8s,
    update_traps_secrets_compose,
    upgrade_docker_compose,
    upgrade_helm_microk8s,
    wait_for_containers_initialization,
    wait_for_pod_initialization_microk8s,
)

logger = logging.getLogger(__name__)


async def send_trap(
    host, port, object_identity, mib_to_load, community, mp_model, *var_binds
):
    error_indication, error_status, error_index, varBinds = await send_notification(
        SnmpEngine(),
        CommunityData(community, mpModel=mp_model),
        await UdpTransportTarget.create((host, port)),
        ContextData(),
        "trap",
        NotificationType(ObjectIdentity(object_identity))
        .add_varbinds(*var_binds)
        .load_mibs(mib_to_load),
    )

    if error_indication:
        logger.error(f"{error_indication}")


async def send_v3_trap(host, port, object_identity, *var_binds):
    error_indication, error_status, error_index, varBinds = await send_notification(
        SnmpEngine(OctetString(hexValue="80003a8c04")),
        UsmUserData(
            userName="snmp-poller",
            authKey="PASSWORD1",
            privKey="PASSWORD1",
            authProtocol=USM_AUTH_HMAC96_SHA,
            privProtocol=USM_PRIV_CBC56_DES,
        ),
        await UdpTransportTarget.create((host, port)),
        ContextData(),
        "trap",
        NotificationType(ObjectIdentity(object_identity)).add_varbinds(*var_binds),
    )

    if error_indication:
        logger.error(f"{error_indication}")


@pytest.mark.part6
@pytest.mark.asyncio
async def test_trap_v1(request, setup_splunk):
    trap_external_ip = request.config.getoption("trap_external_ip")
    logger.info(f"I have: {trap_external_ip}")

    await asyncio.sleep(2)
    # send trap
    varbind1 = ("1.3.6.1.6.3.1.1.4.3.0", "1.3.6.1.4.1.20408.4.1.1.2")
    varbind2 = ("1.3.6.1.2.1.1.4.0", OctetString("my contact"))
    await send_trap(
        trap_external_ip,
        162,
        "1.3.6.1.6.3.1.1.5.2",
        "SNMPv2-MIB",
        "publicv1",
        0,
        varbind1,
        varbind2,
    )

    # wait for the message to be processed
    await asyncio.sleep(5)

    search_query = """search index="netops" sourcetype="sc4snmp:traps" earliest=-1m
                     | head 1"""

    result_count, events_count = splunk_single_search(setup_splunk, search_query)

    assert result_count == 1


@pytest.mark.part6
@pytest.mark.asyncio
async def test_trap_v2(request, setup_splunk):
    trap_external_ip = request.config.getoption("trap_external_ip")
    logger.info(f"I have: {trap_external_ip}")

    await asyncio.sleep(2)
    # send trap
    varbind1 = ("1.3.6.1.6.3.1.1.4.3.0", "1.3.6.1.4.1.20408.4.1.1.2")
    varbind2 = ("1.3.6.1.2.1.1.1.0", OctetString("my system"))
    await send_trap(
        trap_external_ip,
        162,
        "1.3.6.1.6.3.1.1.5.2",
        "SNMPv2-MIB",
        "homelab",
        1,
        varbind1,
        varbind2,
    )

    # wait for the message to be processed
    await asyncio.sleep(5)

    search_query = """search index="netops" sourcetype="sc4snmp:traps" earliest=-1m
                     | head 1"""

    result_count, events_count = splunk_single_search(setup_splunk, search_query)

    assert result_count == 1


@pytest.mark.part6
@pytest.mark.asyncio
async def test_added_varbind(request, setup_splunk):
    trap_external_ip = request.config.getoption("trap_external_ip")
    logger.info(f"I have: {trap_external_ip}")

    await asyncio.sleep(2)
    # send trap
    varbind1 = ("1.3.6.1.2.1.1.1.0", OctetString("test_added_varbind"))
    await send_trap(
        trap_external_ip, 162, "1.3.6.1.2.1.2.1", "SNMPv2-MIB", "public", 1, varbind1
    )

    # wait for the message to be processed
    await asyncio.sleep(5)

    search_query = (
        """search index="netops" "SNMPv2-MIB.sysDescr.value"="test_added_varbind" """
    )

    result_count, events_count = splunk_single_search(setup_splunk, search_query)

    assert result_count == 1


@pytest.mark.part6
@pytest.mark.asyncio
async def test_many_traps(request, setup_splunk):
    trap_external_ip = request.config.getoption("trap_external_ip")
    logger.info(f"I have: {trap_external_ip}")

    await asyncio.sleep(2)
    # send trap
    varbind1 = ("1.3.6.1.2.1.1.1.0", OctetString("test_many_traps"))
    for _ in range(5):
        await send_trap(
            trap_external_ip,
            162,
            "1.3.6.1.2.1.2.1",
            "SNMPv2-MIB",
            "public",
            1,
            varbind1,
        )

    # wait for the message to be processed
    await asyncio.sleep(5)

    search_query = (
        """search index="netops" "SNMPv2-MIB.sysDescr.value"="test_many_traps" """
    )

    result_count, events_count = splunk_single_search(setup_splunk, search_query)

    assert result_count == 5


@pytest.mark.part6
@pytest.mark.asyncio
async def test_more_than_one_varbind(request, setup_splunk):
    trap_external_ip = request.config.getoption("trap_external_ip")
    logger.info(f"I have: {trap_external_ip}")

    await asyncio.sleep(2)
    # send trap
    varbind1 = ("1.3.6.1.2.1.1.4.0", OctetString("test_more_than_one_varbind_contact"))
    varbind2 = ("1.3.6.1.2.1.1.1.0", OctetString("test_more_than_one_varbind"))
    await send_trap(
        trap_external_ip,
        162,
        "1.3.6.1.2.1.2.1",
        "SNMPv2-MIB",
        "public",
        1,
        varbind1,
        varbind2,
    )

    # wait for the message to be processed
    await asyncio.sleep(2)

    search_query = """search index="netops" | search "SNMPv2-MIB.sysDescr.value"="test_more_than_one_varbind"
    "SNMPv2-MIB.sysContact.value"=test_more_than_one_varbind_contact """

    result_count, events_count = splunk_single_search(setup_splunk, search_query)

    assert result_count == 1


@pytest.mark.part6
@pytest.mark.asyncio
async def test_loading_mibs(request, setup_splunk):
    trap_external_ip = request.config.getoption("trap_external_ip")
    logger.info(f"I have: {trap_external_ip}")

    await asyncio.sleep(2)
    # send trap
    varbind1 = ("1.3.6.1.6.3.1.1.4.1.0", "1.3.6.1.4.1.15597.1.1.1.1.0.1")
    await send_trap(
        trap_external_ip,
        162,
        "1.3.6.1.4.1.15597.1.1.1.1",
        "SNMPv2-MIB",
        "public",
        1,
        varbind1,
    )

    # wait for the message to be processed
    await asyncio.sleep(2)

    search_query = """search index=netops "SNMPv2-MIB.snmpTrapOID.value"="AVAMAR-MCS-MIB::eventTrap"  """

    result_count, events_count = splunk_single_search(setup_splunk, search_query)

    assert result_count == 1


def mask_ip(line: str) -> str:
    line = re.sub(r"(\d{1,3}\.){3}\d{1,3}", "XXX.XXX.XXX.XXX", line)
    line = re.sub(
        r"([0-9a-fA-F]{0,4}:){1,7}[0-9a-fA-F]{0,4}",
        "XXXX:XXXX:XXXX:XXXX:XXXX:XXXX:XXXX:XXXX",
        line,
    )
    return line


def log_trap_errors_microk8s():
    pods_cmd = "sudo microk8s kubectl get pods -n sc4snmp --no-headers | awk '/snmp-splunk-connect-for-snmp-trap/ {print $1}'"
    pods = os.popen(pods_cmd).read().splitlines()

    for pod in pods:
        logs_cmd = f"sudo microk8s kubectl logs -n sc4snmp {pod} --tail=200"
        logs = os.popen(logs_cmd).read().splitlines()
        for line in logs:
            print(mask_ip(line))


def log_trap_errors_docker():
    containers_cmd = (
        "sudo docker ps --format '{{.Names}}' | grep snmp-splunk-connect-for-snmp-trap"
    )
    containers = os.popen(containers_cmd).read().splitlines()

    for container in containers:
        logs_cmd = f"sudo docker logs --tail 200 {container}"
        logs = os.popen(logs_cmd).read().splitlines()
        for line in logs:
            print(mask_ip(line))


@pytest.mark.part6
@pytest.mark.asyncio
async def test_trap_v3(request, setup_splunk):
    trap_external_ip = request.config.getoption("trap_external_ip")
    deployment = request.config.getoption("sc4snmp_deployment")
    if deployment == "microk8s":
        create_v3_secrets_microk8s()
        update_file_microk8s(["- secretv4"], "traps_secrets.yaml")
        upgrade_helm_microk8s(["traps_secrets.yaml"])
    else:
        create_v3_secrets_compose()
        update_traps_secrets_compose(["secretv4"])
        upgrade_docker_compose()
    logger.info(f"I have: {trap_external_ip}")
    if deployment == "microk8s":
        wait_for_pod_initialization_microk8s()
    else:
        wait_for_containers_initialization()
    await asyncio.sleep(20)
    # send trap
    varbind1 = ("1.3.6.1.2.1.1.4.0", OctetString("test_trap_v3"))
    await send_v3_trap(trap_external_ip, 162, "1.3.6.1.2.1.1.0", varbind1)

    # wait for the message to be processed
    await asyncio.sleep(5)

    search_query = (
        """search index=netops "SNMPv2-MIB.sysContact.value"="test_trap_v3"  """
    )

    result_count, events_count = splunk_single_search(setup_splunk, search_query)

    if deployment == "microk8s":
        log_trap_errors_microk8s()
    else:
        log_trap_errors_docker()

    assert result_count == 1
