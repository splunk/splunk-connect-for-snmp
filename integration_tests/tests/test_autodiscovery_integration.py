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
    usmHMACSHAAuthProtocol,
)

DISCOVERY_OUTPUT_DIR = Path(
    os.getenv(
        "AUTODISCOVERY_OUTPUT_DIR",
        Path(__file__).resolve().parents[1] / "discovery",
    )
)
DISCOVERY_CSV = DISCOVERY_OUTPUT_DIR / "discovery_devices.csv"
SIMULATOR_PROFILES = {
    "microk8s": {
        "namespace": "microk8s-agent-simulator",
        "prefixes": ("10.1.1", "10.2.2"),
    },
    "docker-compose": {
        "namespace": "docker-agent-simulator",
        "prefixes": ("10.4.4", "10.5.5"),
    },
}
DISCOVERY_VARIATIONS = {
    "integration_v2c": {
        "agent_prefix": "v1",
        "variation": "v2c",
        "version": "2c",
        "community": "public",
        "secret": "",
        "group": "autodiscovery-v2c",
    },
    "integration_v3": {
        "agent_prefix": "v2",
        "variation": "v3",
        "version": "3",
        "community": "",
        "secret": "autodiscovery-v3-sha-aes",
        "group": "autodiscovery-v3-sha",
    },
}


def build_expected_by_key(prefixes):
    expected = {}
    for prefix, (discovery_key, variation) in zip(
        prefixes, DISCOVERY_VARIATIONS.items()
    ):
        details = variation.copy()
        agent_prefix = details.pop("agent_prefix")
        expected[discovery_key] = {
            "ips": {f"{prefix}.{index}" for index in range(1, 4)},
            "names": {
                f"snmp-agent-{agent_prefix}-{index:03d}" for index in range(1, 4)
            },
            "subnet": f"{prefix}.0/29",
            **details,
        }
    return expected


EXPECTED_DEVICE_COUNT = 6
AUTODISCOVERY_PORT = 161
AUTODISCOVERY_COMPLETION_TIMEOUT = 500
REMOVABLE_SIMULATOR_NAME = "snmp-agent-v1-003"
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


@pytest.fixture(scope="module")
def deployment(request):
    return request.config.getoption("sc4snmp_deployment")


@pytest.fixture(scope="module")
def simulator_profile(deployment):
    assert deployment in SIMULATOR_PROFILES, f"Unsupported deployment: {deployment}"
    profile = SIMULATOR_PROFILES[deployment]
    return {
        **profile,
        "namespace": os.getenv(
            "AUTODISCOVERY_SIMULATOR_NAMESPACE", profile["namespace"]
        ),
        "expected_by_key": build_expected_by_key(profile["prefixes"]),
    }


@pytest.fixture(scope="module")
def expected_by_key(simulator_profile):
    return simulator_profile["expected_by_key"]


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
    return len(rows) == EXPECTED_DEVICE_COUNT and all(
        {row["ip"] for row in rows if row.get("key") == discovery_key} == agents["ips"]
        for discovery_key, agents in deployed_agents.items()
    )


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
def deployed_agents(simulator_profile, expected_by_key):
    pod_list = json.loads(
        run_checked(
            [
                "sudo",
                "microk8s",
                "kubectl",
                "get",
                "pods",
                "-n",
                simulator_profile["namespace"],
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

    key_by_variation = {
        expected["variation"]: discovery_key
        for discovery_key, expected in expected_by_key.items()
    }
    deployed = {
        discovery_key: {"ips": set(), "names": set()}
        for discovery_key in expected_by_key
    }
    for agent in agents:
        discovery_key = key_by_variation.get(agent["variation"])
        assert discovery_key, f"Unexpected simulator variation: {agent}"
        deployed[discovery_key]["ips"].add(agent["ip"])
        deployed[discovery_key]["names"].add(agent["name"])

    assert len(agents) == EXPECTED_DEVICE_COUNT
    for discovery_key, expected in expected_by_key.items():
        assert deployed[discovery_key]["ips"] == expected["ips"]
        assert deployed[discovery_key]["names"] == expected["names"]

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


def rerun_v2c_discovery(deployment, v2c_subnet):
    discovery_script = f"""
from splunk_connect_for_snmp.common.discovery_record import DiscoveryRecord
from splunk_connect_for_snmp.discovery.discovery_manager import Discovery

record = DiscoveryRecord(
    discovery_name="integration_v2c",
    network_address="{v2c_subnet}",
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


def stop_removable_simulator(simulator_namespace):
    network_policy = {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {
            "name": OFFLINE_NETWORK_POLICY,
            "namespace": simulator_namespace,
            "labels": {"sc4snmp.integration.autodiscovery": "true"},
        },
        "spec": {
            "podSelector": {"matchLabels": {"agent-id": REMOVABLE_SIMULATOR_NAME}},
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


def start_removable_simulator(simulator_namespace):
    run_checked(
        [
            "sudo",
            "microk8s",
            "kubectl",
            "delete",
            "networkpolicy",
            OFFLINE_NETWORK_POLICY,
            "-n",
            simulator_namespace,
            "--ignore-not-found=true",
        ]
    )
    time.sleep(2)


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
    discovered_rows, deployed_agents, expected_by_key
):
    assert len(discovered_rows) == EXPECTED_DEVICE_COUNT

    for discovery_key, expected in expected_by_key.items():
        rows = [row for row in discovered_rows if row["key"] == discovery_key]
        csv_ips = {row["ip"] for row in rows}
        assert csv_ips == deployed_agents[discovery_key]["ips"]
        assert csv_ips == expected["ips"]
        assert deployed_agents[discovery_key]["names"] == expected["names"]
        assert {row["subnet"] for row in rows} == {expected["subnet"]}


@pytest.mark.part7
def test_autodiscovery_records_v2c_and_v3_credentials(discovered_rows, expected_by_key):
    for discovery_key, expected in expected_by_key.items():
        rows = [row for row in discovered_rows if row["key"] == discovery_key]
        assert {row["version"] for row in rows} == {expected["version"]}
        assert {row["community"] for row in rows} == {expected["community"]}
        assert {row["secret"] for row in rows} == {expected["secret"]}
        assert {row["port"] for row in rows} == {str(AUTODISCOVERY_PORT)}


@pytest.mark.part7
def test_autodiscovery_applies_sysdescr_device_rules(discovered_rows, expected_by_key):
    for discovery_key, expected in expected_by_key.items():
        groups = {
            row["group"] for row in discovered_rows if row["key"] == discovery_key
        }
        assert groups == {expected["group"]}


@pytest.mark.part7
def test_delete_already_discovered_removes_offline_device(
    deployment, discovered_rows, simulator_profile, expected_by_key
):
    v2c_configuration = expected_by_key["integration_v2c"]
    expected_ips = v2c_configuration["ips"]
    removable_simulator_ip = f'{simulator_profile["prefixes"][0]}.3'
    expected_without_offline_device = expected_ips - {removable_simulator_ip}

    # Do not seed or edit discovery_devices.csv in the test. Changing device
    # availability lets the deployed discovery feature own every CSV write.
    stop_removable_simulator(simulator_profile["namespace"])
    try:
        rerun_v2c_discovery(deployment, v2c_configuration["subnet"])
        wait_for_discovery_ips("integration_v2c", expected_without_offline_device)
    finally:
        start_removable_simulator(simulator_profile["namespace"])
        wait_for_v2c_simulator(removable_simulator_ip)
        rerun_v2c_discovery(deployment, v2c_configuration["subnet"])
        wait_for_discovery_ips("integration_v2c", expected_ips)


@pytest.mark.part7
@pytest.mark.asyncio
async def test_get_cmd_resolves_base_mib_oids_from_simulator_ips(
    discovered_rows, simulator_profile
):
    requests = (
        (
            f'{simulator_profile["prefixes"][0]}.1',
            CommunityData("public", mpModel=1),
            "autodiscovery integration v2c",
        ),
        (
            f'{simulator_profile["prefixes"][1]}.1',
            UsmUserData(
                "autodiscovery-sha",
                authKey="AuthPass1",
                privKey="PrivPass1",
                authProtocol=usmHMACSHAAuthProtocol,
                privProtocol=usmAesCfb128Protocol,
            ),
            "autodiscovery integration v3 SHA",
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
