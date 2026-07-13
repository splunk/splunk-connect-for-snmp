import asyncio
import csv
import json
import os
import subprocess
import time
from pathlib import Path

import pytest
from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    get_cmd,
    usmAesCfb128Protocol,
    usmHMACMD5AuthProtocol,
    usmHMACSHAAuthProtocol,
)

DISCOVERY_OUTPUT_DIR = Path(
    os.getenv(
        "AUTODISCOVERY_OUTPUT_DIR",
        Path(__file__).resolve().parents[1] / "discovery",
    )
)
DISCOVERY_CSV = DISCOVERY_OUTPUT_DIR / "discovery_devices.csv"
EXPECTED_BY_KEY = {
    "integration_v2c": {
        "ips": {f"10.1.1.{index}" for index in range(1, 10)},
        "names": {f"snmp-agent-v1-{index:03d}" for index in range(1, 10)},
        "subnet": "10.1.1.0/24",
        "variation": "v2c",
        "version": "2c",
        "community": "public",
        "secret": "",
        "group": "autodiscovery-v2c",
    },
    "integration_v3_sha": {
        "ips": {f"10.2.2.{index}" for index in range(1, 6)},
        "names": {f"snmp-agent-v2-{index:03d}" for index in range(1, 6)},
        "subnet": "10.2.2.0/24",
        "variation": "v3-sha",
        "version": "3",
        "community": "",
        "secret": "autodiscovery-v3-sha-aes",
        "group": "autodiscovery-v3-sha",
    },
    "integration_v3_md5": {
        "ips": {f"10.2.2.{index}" for index in range(6, 10)},
        "names": {f"snmp-agent-v2-{index:03d}" for index in range(6, 10)},
        "subnet": "10.2.2.0/24",
        "variation": "v3-md5",
        "version": "3",
        "community": "",
        "secret": "autodiscovery-v3-md5-aes",
        "group": "autodiscovery-v3-md5",
    },
}
EXPECTED_DEVICE_COUNT = sum(
    len(configuration["ips"]) for configuration in EXPECTED_BY_KEY.values()
)
AUTODISCOVERY_PORT = 161
AUTODISCOVERY_COMPLETION_TIMEOUT = 500
SIMULATOR_NAMESPACE = os.getenv("AUTODISCOVERY_SIMULATOR_NAMESPACE", "agent-simulator")
DOCKER_SIMULATOR_NETWORKS = {
    "v2c": os.getenv(
        "AUTODISCOVERY_DOCKER_NETWORK_V1", "sc4snmp-autodiscovery-v1"
    ),
    "v3-sha": os.getenv(
        "AUTODISCOVERY_DOCKER_NETWORK_V2", "sc4snmp-autodiscovery-v2"
    ),
    "v3-md5": os.getenv(
        "AUTODISCOVERY_DOCKER_NETWORK_V2", "sc4snmp-autodiscovery-v2"
    ),
}
REMOVABLE_SIMULATOR_NAME = "snmp-agent-v1-009"
REMOVABLE_SIMULATOR_IP = "10.1.1.9"
OFFLINE_NETWORK_POLICY = "autodiscovery-offline-agent"
BASE_OID_SPECS = (
    # Use the same symbolic SNMPv2-MIB lookup as Discovery.check_snmp_device.
    # This makes the integration test fail if the runtime can no longer load
    # the MIB or resolve the objects before sending get_cmd.
    ("SNMPv2-MIB", "sysDescr", 0),
    ("SNMPv2-MIB", "sysObjectID", 0),
    ("SNMPv2-MIB", "sysUpTime", 0),
    ("SNMPv2-MIB", "sysName", 0),
    # Keep this numeric because IF-MIB is supplied by the SC4SNMP MIB server,
    # while this test also runs directly from the local Poetry environment.
    ("1.3.6.1.2.1.2.1.0",),
)


def read_discovery_rows():
    if not DISCOVERY_CSV.is_file():
        return []
    try:
        with DISCOVERY_CSV.open(newline="", encoding="utf-8") as csv_file:
            return list(csv.DictReader(csv_file))
    except (OSError, csv.Error):
        # The worker rewrites the file under its own lock. A host-side read can
        # briefly overlap that replacement, so retry until the module timeout.
        return []


def has_complete_matrix(rows, deployed_agents):
    if len(rows) != EXPECTED_DEVICE_COUNT:
        return False
    for discovery_key in EXPECTED_BY_KEY:
        actual_ips = {row["ip"] for row in rows if row.get("key") == discovery_key}
        if actual_ips != deployed_agents[discovery_key]["ips"]:
            return False
    return True


@pytest.fixture(scope="module")
def discovered_rows(deployed_agents):
    deadline = time.monotonic() + AUTODISCOVERY_COMPLETION_TIMEOUT
    last_rows = []
    while time.monotonic() < deadline:
        last_rows = read_discovery_rows()
        if has_complete_matrix(last_rows, deployed_agents):
            return last_rows
        time.sleep(2)

    pytest.fail(
        f"Autodiscovery did not produce the expected {EXPECTED_DEVICE_COUNT}-device "
        f"matrix within {AUTODISCOVERY_COMPLETION_TIMEOUT} seconds. "
        f"CSV={DISCOVERY_CSV}; rows={last_rows}"
    )


def run_checked(command, input_text=None):
    result = subprocess.run(
        command,
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"Command failed: {' '.join(command)}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    return result.stdout.strip()


@pytest.fixture(scope="module")
def deployed_agents(request):
    deployment = request.config.getoption("sc4snmp_deployment")
    agents = []

    if deployment == "microk8s":
        pod_list = json.loads(
            run_checked(
                [
                    "sudo",
                    "microk8s",
                    "kubectl",
                    "get",
                    "pods",
                    "-n",
                    SIMULATOR_NAMESPACE,
                    "-l",
                    "sc4snmp.integration.autodiscovery=true",
                    "-o",
                    "json",
                ]
            )
        )
        agents = [
            {
                "name": item["metadata"]["name"],
                "ip": item["status"].get("podIP", ""),
                "variation": item["metadata"]["labels"]["variation"],
            }
            for item in pod_list["items"]
        ]
    else:
        container_ids = run_checked(
            [
                "sudo",
                "docker",
                "ps",
                "-aq",
                "--filter",
                "label=sc4snmp.integration.autodiscovery=true",
            ]
        ).splitlines()
        assert container_ids, "No Docker autodiscovery simulator containers found"
        containers = json.loads(
            run_checked(["sudo", "docker", "inspect", *container_ids])
        )
        for container in containers:
            variation = container["Config"]["Labels"][
                "sc4snmp.integration.variation"
            ]
            network = DOCKER_SIMULATOR_NETWORKS[variation]
            agents.append(
                {
                    "name": container["Name"].lstrip("/"),
                    "ip": container["NetworkSettings"]["Networks"][network][
                        "IPAddress"
                    ],
                    "variation": variation,
                }
            )

    key_by_variation = {
        expected["variation"]: discovery_key
        for discovery_key, expected in EXPECTED_BY_KEY.items()
    }
    deployed = {
        discovery_key: {"ips": set(), "names": set()}
        for discovery_key in EXPECTED_BY_KEY
    }
    for agent in agents:
        discovery_key = key_by_variation.get(agent["variation"])
        assert discovery_key, f"Unexpected simulator variation: {agent}"
        deployed[discovery_key]["ips"].add(agent["ip"])
        deployed[discovery_key]["names"].add(agent["name"])

    assert len(agents) == EXPECTED_DEVICE_COUNT
    for discovery_key, expected in EXPECTED_BY_KEY.items():
        assert deployed[discovery_key]["ips"] == expected["ips"]
        assert deployed[discovery_key]["names"] == expected["names"]

    v1_ips = deployed["integration_v2c"]["ips"]
    v2_ips = (
        deployed["integration_v3_sha"]["ips"]
        | deployed["integration_v3_md5"]["ips"]
    )
    assert v1_ips == {f"10.1.1.{index}" for index in range(1, 10)}
    assert v2_ips == {f"10.2.2.{index}" for index in range(1, 10)}
    return deployed


def discovery_worker_exec_prefix(deployment):
    if deployment == "microk8s":
        pod_name = run_checked(
            [
                "sudo",
                "microk8s",
                "kubectl",
                "get",
                "pod",
                "-n",
                "sc4snmp",
                "-l",
                "app.kubernetes.io/component=worker-discovery",
                "--field-selector=status.phase=Running",
                "-o",
                "jsonpath={.items[0].metadata.name}",
            ]
        )
        assert pod_name, "No running MicroK8s discovery worker found"
        return [
            "sudo",
            "microk8s",
            "kubectl",
            "exec",
            "-n",
            "sc4snmp",
            pod_name,
            "--",
        ]

    container_name = run_checked(
        [
            "sudo",
            "docker",
            "ps",
            "--filter",
            "label=com.docker.compose.service=worker-discovery",
            "--format",
            "{{.Names}}",
        ]
    ).splitlines()
    assert container_name, "No running Docker Compose discovery worker found"
    return ["sudo", "docker", "exec", container_name[0]]


def rerun_v2c_discovery(deployment):
    discovery_script = f"""
from splunk_connect_for_snmp.common.discovery_record import DiscoveryRecord
from splunk_connect_for_snmp.discovery.discovery_manager import Discovery

record = DiscoveryRecord(
    discovery_name="integration_v2c",
    network_address="10.1.1.0/24",
    address=None,
    port={AUTODISCOVERY_PORT},
    version="2c",
    community="public",
    secret=None,
    security_engine="",
    frequency=21600,
    delete_already_discovered=True,
    device_rules=[{{
        "name": "integration-v2c-agents",
        "patterns": "*autodiscovery integration v2c*",
        "group": "autodiscovery-v2c",
    }}],
)
result = Discovery().do_work(record)
print(f"discovered={{len(result)}}")
"""
    output = run_checked(
        discovery_worker_exec_prefix(deployment)
        + ["/app/.venv/bin/python", "-c", discovery_script]
    )
    assert "discovered=" in output


def wait_for_discovery_ips(
    discovery_key, expected_ips, timeout=AUTODISCOVERY_COMPLETION_TIMEOUT
):
    deadline = time.monotonic() + timeout
    last_ips = set()
    while time.monotonic() < deadline:
        last_ips = {
            row["ip"]
            for row in read_discovery_rows()
            if row.get("key") == discovery_key
        }
        if last_ips == expected_ips:
            return
        time.sleep(1)
    pytest.fail(
        f"Discovery key {discovery_key} did not reach expected IPs "
        f"{expected_ips}; last IPs={last_ips}"
    )


def wait_for_v2c_simulator(address, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = subprocess.run(
            [
                "snmpget",
                "-v2c",
                "-c",
                "public",
                "-On",
                f"{address}:{AUTODISCOVERY_PORT}",
                "1.3.6.1.2.1.1.1.0",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(1)
    pytest.fail(f"Simulator {address}:{AUTODISCOVERY_PORT} did not become ready")


def stop_removable_simulator(deployment):
    if deployment == "microk8s":
        network_policy = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {
                "name": OFFLINE_NETWORK_POLICY,
                "namespace": SIMULATOR_NAMESPACE,
                "labels": {"sc4snmp.integration.autodiscovery": "true"},
            },
            "spec": {
                "podSelector": {
                    "matchLabels": {"agent-id": REMOVABLE_SIMULATOR_NAME}
                },
                "policyTypes": ["Ingress"],
            },
        }
        run_checked(
            [
                "sudo",
                "microk8s",
                "kubectl",
                "apply",
                "-f",
                "-",
            ],
            input_text=json.dumps(network_policy),
        )
        time.sleep(2)
        return

    run_checked(["sudo", "docker", "stop", REMOVABLE_SIMULATOR_NAME])


def start_removable_simulator(deployment):
    if deployment == "microk8s":
        run_checked(
            [
                "sudo",
                "microk8s",
                "kubectl",
                "delete",
                "networkpolicy",
                OFFLINE_NETWORK_POLICY,
                "-n",
                SIMULATOR_NAMESPACE,
                "--ignore-not-found=true",
            ]
        )
        time.sleep(2)
        return

    run_checked(["sudo", "docker", "start", REMOVABLE_SIMULATOR_NAME])


async def fetch_base_oids(address, auth_data):
    snmp_engine = SnmpEngine()
    try:
        result = await get_cmd(
            snmp_engine,
            auth_data,
            await UdpTransportTarget.create(
                (address, AUTODISCOVERY_PORT), timeout=2, retries=2
            ),
            ContextData(),
            *(ObjectType(ObjectIdentity(*oid_spec)) for oid_spec in BASE_OID_SPECS),
        )
        return result
    finally:
        snmp_engine.close_dispatcher()


@pytest.mark.part7
def test_autodiscovery_csv_matches_all_deployed_agents(
    discovered_rows, deployed_agents
):
    assert EXPECTED_DEVICE_COUNT == 18
    assert len(EXPECTED_BY_KEY) == 3
    assert len(discovered_rows) == EXPECTED_DEVICE_COUNT

    for discovery_key, expected in EXPECTED_BY_KEY.items():
        rows = [row for row in discovered_rows if row["key"] == discovery_key]
        csv_ips = {row["ip"] for row in rows}
        assert csv_ips == deployed_agents[discovery_key]["ips"]
        assert csv_ips == expected["ips"]
        assert deployed_agents[discovery_key]["names"] == expected["names"]
        assert {row["subnet"] for row in rows} == {expected["subnet"]}


@pytest.mark.part7
def test_autodiscovery_records_v2c_and_v3_credentials(discovered_rows):
    for discovery_key, expected in EXPECTED_BY_KEY.items():
        rows = [row for row in discovered_rows if row["key"] == discovery_key]
        assert {row["version"] for row in rows} == {expected["version"]}
        assert {row["community"] for row in rows} == {expected["community"]}
        assert {row["secret"] for row in rows} == {expected["secret"]}
        assert {row["port"] for row in rows} == {str(AUTODISCOVERY_PORT)}


@pytest.mark.part7
def test_autodiscovery_applies_sysdescr_device_rules(discovered_rows):
    for discovery_key, expected in EXPECTED_BY_KEY.items():
        groups = {
            row["group"] for row in discovered_rows if row["key"] == discovery_key
        }
        assert groups == {expected["group"]}


@pytest.mark.part7
def test_delete_already_discovered_removes_offline_device(request, discovered_rows):
    del discovered_rows
    deployment = request.config.getoption("sc4snmp_deployment")
    expected_ips = EXPECTED_BY_KEY["integration_v2c"]["ips"]
    expected_without_offline_device = expected_ips - {REMOVABLE_SIMULATOR_IP}

    # Do not seed or edit discovery_devices.csv in the test. Changing device
    # availability lets the deployed discovery feature own every CSV write.
    stop_removable_simulator(deployment)
    try:
        rerun_v2c_discovery(deployment)
        wait_for_discovery_ips("integration_v2c", expected_without_offline_device)
    finally:
        start_removable_simulator(deployment)
        wait_for_v2c_simulator(REMOVABLE_SIMULATOR_IP)
        rerun_v2c_discovery(deployment)
        wait_for_discovery_ips("integration_v2c", expected_ips)


@pytest.mark.part7
@pytest.mark.asyncio
async def test_get_cmd_resolves_base_mib_oids_from_simulator_ips(discovered_rows):
    del discovered_rows
    requests = (
        (
            "10.1.1.1",
            CommunityData("public", mpModel=1),
            "autodiscovery integration v2c",
        ),
        (
            "10.2.2.1",
            UsmUserData(
                "autodiscovery-sha",
                authKey="AuthPass1",
                privKey="PrivPass1",
                authProtocol=usmHMACSHAAuthProtocol,
                privProtocol=usmAesCfb128Protocol,
            ),
            "autodiscovery integration v3 SHA",
        ),
        (
            "10.2.2.6",
            UsmUserData(
                "autodiscovery-md5",
                authKey="AuthPass2",
                privKey="PrivPass2",
                authProtocol=usmHMACMD5AuthProtocol,
                privProtocol=usmAesCfb128Protocol,
            ),
            "autodiscovery integration v3 MD5",
        ),
    )

    responses = await asyncio.gather(
        *(fetch_base_oids(address, auth_data) for address, auth_data, _ in requests)
    )
    for response, (_, _, expected_description) in zip(responses, requests):
        error_indication, error_status, error_index, var_binds = response
        assert error_indication is None
        assert not error_status, f"SNMP error at index {error_index}: {error_status}"
        assert len(var_binds) == len(BASE_OID_SPECS)
        assert var_binds[0][0].prettyPrint() == "SNMPv2-MIB::sysDescr.0"
        assert expected_description in var_binds[0][1].prettyPrint()
        assert var_binds[3][1].prettyPrint().startswith("autodiscovery-")
        assert var_binds[4][1].prettyPrint() == "1"
