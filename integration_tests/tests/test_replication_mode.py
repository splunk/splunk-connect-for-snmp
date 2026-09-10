import base64
import hashlib
import json
import logging
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import pytest
from pysnmp.hlapi import (
    CommunityData,
    ContextData,
    NotificationType,
    ObjectIdentity,
    OctetString,
    SnmpEngine,
    UdpTransportTarget,
    sendNotification,
)

from integration_tests.utils.splunk_test_utils import wait_for_splunk_search

logger = logging.getLogger(__name__)
pytestmark = pytest.mark.part7

REPO_ROOT = Path(__file__).resolve().parents[2]
CHART_PATH = REPO_ROOT / "charts" / "splunk-connect-for-snmp"
DEFAULT_VALUES_PATH = REPO_ROOT / "integration_tests" / "values.yaml"
MONGODB_REPLICA_KEY = "replica-key"
POLL_PROFILE = "mongodb_auth_transition"


@dataclass(frozen=True)
class ReplicationDeployment:
    namespace: str
    release: str
    replica_count: int
    replica_key_digest_before_noop_upgrade: str
    replica_key_digest_after_noop_upgrade: str
    pod_uids_before_noop_upgrade: dict[str, str]
    pod_uids_after_noop_upgrade: dict[str, str]
    transition_started_at: int
    poll_target: str
    trap_host: str
    trap_port: int


def _run(command, *, check=True, timeout=600):
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if check and result.returncode:
        raise AssertionError(
            f"Command failed with exit code {result.returncode}: {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _kubectl(namespace, *arguments, check=True, timeout=600):
    return _run(
        ["sudo", "microk8s", "kubectl", "--namespace", namespace, *arguments],
        check=check,
        timeout=timeout,
    )


def _helm(*arguments, check=True, timeout=3600):
    result = _run(
        ["sudo", "microk8s", "helm3", *arguments],
        check=check,
        timeout=timeout,
    )
    if result.stdout:
        logger.info("Helm output:\n%s", result.stdout.rstrip())
    return result


def _delete_inventory_job(namespace, release):
    selector = (
        f"app.kubernetes.io/instance={release}," "app.kubernetes.io/component=inventory"
    )
    jobs = _kubectl(
        namespace,
        "get",
        "jobs",
        "--selector",
        selector,
        "--output",
        "name",
    ).stdout.split()
    for job in jobs:
        _kubectl(
            namespace,
            "wait",
            "--for=condition=complete",
            job,
            "--timeout=10m",
            timeout=660,
        )
        _kubectl(namespace, "delete", job, "--wait=true")


def _mongodb_pod_uids(namespace, release):
    pods = json.loads(
        _kubectl(
            namespace,
            "get",
            "pods",
            "--selector",
            f"app={release}-mongodb",
            "--output",
            "json",
        ).stdout
    )
    return {item["metadata"]["name"]: item["metadata"]["uid"] for item in pods["items"]}


def _replica_key(namespace, release):
    return _kubectl(
        namespace,
        "get",
        f"secret/{release}-mongodb-replicakey",
        "--output",
        f"jsonpath={{.data.{MONGODB_REPLICA_KEY}}}",
    ).stdout


def _replica_key_digest(encoded_key):
    try:
        decoded_key = base64.b64decode(encoded_key, validate=True).decode()
    except (ValueError, UnicodeDecodeError) as error:
        raise AssertionError("MongoDB replica key is not valid base64 text") from error
    if not re.fullmatch(r"[A-Za-z0-9]{64}", decoded_key):
        raise AssertionError("MongoDB replica key is not 64 alphanumeric characters")
    return hashlib.sha256(decoded_key.encode()).hexdigest()


def _mongodb_eval(namespace, release, script, *, authenticated=True, check=True):
    pod = f"{release}-mongodb-0"
    command = [
        "exec",
        pod,
        "--container",
        "mongodb",
        "--",
        "sh",
        "-ec",
    ]
    if authenticated:
        command.append(
            'exec mongosh --quiet --username "$MONGO_INITDB_ROOT_USERNAME" '
            '--password "$MONGO_INITDB_ROOT_PASSWORD" '
            '--authenticationDatabase admin --eval "$1"'
        )
    else:
        command.append('exec mongosh --quiet --eval "$1"')
    command.extend(["mongosh", script])
    return _kubectl(namespace, *command, check=check)


def _write_override_file(poll_target):
    override = f"""\
scheduler:
  groups: |
    {{}}
  profiles: |
    {POLL_PROFILE}:
      frequency: 5
      varBinds:
        - ["SNMPv2-MIB", "sysDescr", 0]
poller:
  enableFullWalk: false
  usernameSecrets: []
  inventory: |
    address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
    {poll_target},1166,2c,public,,,600,{POLL_PROFILE},,
traps:
  loadBalancerIP: ""
  usernameSecrets: []
  communities:
    2c:
      - public
  service:
    type: NodePort
    usemetallb: false
"""
    override_file = tempfile.NamedTemporaryFile(
        mode="w", prefix="sc4snmp-replication-", suffix=".yaml", delete=False
    )
    override_file.write(override)
    override_file.close()
    return Path(override_file.name)


@pytest.fixture(scope="module")
def authenticated_replica_set(request):
    if request.config.getoption("sc4snmp_deployment") != "microk8s":
        pytest.skip("MongoDB authentication transition is a Kubernetes-only test")

    namespace = os.getenv("SC4SNMP_REPLICATION_TEST_NAMESPACE", "sc4snmp-test")
    release = os.getenv("SC4SNMP_REPLICATION_TEST_RELEASE", "snmp-replication-test")
    values_path = Path(
        os.getenv("SC4SNMP_REPLICATION_TEST_VALUES", str(DEFAULT_VALUES_PATH))
    ).resolve()
    poll_target = request.config.getoption("trap_external_ip")
    replica_count = 3
    override_path = _write_override_file(poll_target)
    common_helm_arguments = [
        release,
        str(CHART_PATH),
        "--namespace",
        namespace,
        "--values",
        str(values_path),
        "--values",
        str(override_path),
        "--set",
        "mongodb.mode=replication",
        "--set",
        f"mongodb.replicaCount={replica_count}",
        "--wait",
        "--timeout",
        "50m",
    ]
    image_repository = os.getenv("SC4SNMP_REPLICATION_TEST_IMAGE_REPOSITORY")
    if image_repository:
        common_helm_arguments.extend(
            [
                "--set",
                f"image.repository={image_repository}",
                "--set",
                f"image.tag={os.getenv('SC4SNMP_REPLICATION_TEST_IMAGE_TAG', 'latest')}",
                "--set",
                f"image.pullPolicy={os.getenv('SC4SNMP_REPLICATION_TEST_IMAGE_PULL_POLICY', 'Never')}",
            ]
        )

    _helm("uninstall", release, "--namespace", namespace, check=False)
    _run(
        [
            "sudo",
            "microk8s",
            "kubectl",
            "delete",
            "namespace",
            namespace,
            "--wait=true",
        ],
        check=False,
    )

    try:
        logger.info("Installing an unauthenticated three-member MongoDB replica set")
        _helm(
            "upgrade",
            "--install",
            *common_helm_arguments,
            "--create-namespace",
            "--set",
            "mongodb.auth.enabled=false",
        )

        initial_statefulset = json.loads(
            _kubectl(
                namespace,
                "get",
                f"statefulset/{release}-mongodb",
                "--output",
                "json",
            ).stdout
        )
        initial_args = next(
            container["args"]
            for container in initial_statefulset["spec"]["template"]["spec"][
                "containers"
            ]
            if container["name"] == "mongodb"
        )
        assert "--keyFile" not in initial_args
        assert (
            _mongodb_eval(
                namespace, release, "rs.status().ok", authenticated=False
            ).returncode
            == 0
        )
        assert (
            _kubectl(
                namespace,
                "get",
                f"secret/{release}-mongodb-replicakey",
                check=False,
            ).returncode
            != 0
        )
        logger.info(
            "Initial replica set verified: members=%s authentication=disabled replica-key-secret=absent",
            replica_count,
        )

        # Completed inventory Jobs have immutable Pod templates. Remove the
        # initial Job before changing the MongoDB credentials rendered into it.
        _delete_inventory_job(namespace, release)

        transition_started_at = int(time.time())
        logger.info("Upgrading the replica set from authentication disabled to enabled")
        _helm(
            "upgrade",
            *common_helm_arguments,
            "--set",
            "mongodb.auth.enabled=true",
        )

        for job_name in (
            f"{release}-mongodb-auth-user",
            f"{release}-mongodb-auth-rollout",
        ):
            _kubectl(
                namespace,
                "wait",
                "--for=condition=complete",
                f"job/{job_name}",
                "--timeout=10m",
                timeout=660,
            )
            logger.info("MongoDB transition Job %s completed", job_name)

        replica_key_digest_before_noop_upgrade = _replica_key_digest(
            _replica_key(namespace, release)
        )
        pod_uids_before_noop_upgrade = _mongodb_pod_uids(namespace, release)

        # A normal authenticated upgrade must reuse the live replica key and
        # must not restart MongoDB members.
        _delete_inventory_job(namespace, release)
        _helm(
            "upgrade",
            *common_helm_arguments,
            "--set",
            "mongodb.auth.enabled=true",
        )

        trap_service = f"service/{release}-splunk-connect-for-snmp-trap"
        trap_port = int(
            _kubectl(
                namespace,
                "get",
                trap_service,
                "--output",
                "jsonpath={.spec.ports[0].nodePort}",
            ).stdout
        )

        yield ReplicationDeployment(
            namespace=namespace,
            release=release,
            replica_count=replica_count,
            replica_key_digest_before_noop_upgrade=replica_key_digest_before_noop_upgrade,
            replica_key_digest_after_noop_upgrade=_replica_key_digest(
                _replica_key(namespace, release)
            ),
            pod_uids_before_noop_upgrade=pod_uids_before_noop_upgrade,
            pod_uids_after_noop_upgrade=_mongodb_pod_uids(namespace, release),
            transition_started_at=transition_started_at,
            poll_target=f"{poll_target}:1166",
            trap_host=poll_target,
            trap_port=trap_port,
        )
    finally:
        _helm("uninstall", release, "--namespace", namespace, check=False)
        _run(
            [
                "sudo",
                "microk8s",
                "kubectl",
                "delete",
                "namespace",
                namespace,
                "--wait=true",
            ],
            check=False,
        )
        override_path.unlink(missing_ok=True)


def test_authentication_transition_completes(authenticated_replica_set):
    deployment = authenticated_replica_set
    statefulset = json.loads(
        _kubectl(
            deployment.namespace,
            "get",
            f"statefulset/{deployment.release}-mongodb",
            "--output",
            "json",
        ).stdout
    )
    mongodb_container = next(
        container
        for container in statefulset["spec"]["template"]["spec"]["containers"]
        if container["name"] == "mongodb"
    )
    update_strategy = statefulset["spec"]["updateStrategy"]["type"]
    migration_phase = (
        statefulset["metadata"]
        .get("annotations", {})
        .get("sc4snmp.splunk.com/mongodb-auth-migration-phase")
    )
    keyfile_enabled = "--keyFile" in mongodb_container["args"]
    transition_enabled = "--transitionToAuth" in mongodb_container["args"]
    logger.info(
        "Final MongoDB StatefulSet: updateStrategy=%s migrationPhase=%s keyFile=%s transitionToAuth=%s",
        update_strategy,
        migration_phase or "none",
        keyfile_enabled,
        transition_enabled,
    )

    assert update_strategy == "RollingUpdate"
    assert migration_phase is None
    assert keyfile_enabled
    assert not transition_enabled

    assert (
        deployment.replica_key_digest_after_noop_upgrade
        == deployment.replica_key_digest_before_noop_upgrade
    )
    assert (
        deployment.pod_uids_after_noop_upgrade
        == deployment.pod_uids_before_noop_upgrade
    )
    logger.info(
        "Replica key was preserved and MongoDB Pods were not restarted by the authenticated no-op upgrade"
    )


def test_replica_set_is_healthy_and_requires_authentication(authenticated_replica_set):
    deployment = authenticated_replica_set
    status = json.loads(
        _mongodb_eval(
            deployment.namespace,
            deployment.release,
            "print(JSON.stringify(rs.status().members.map(member => "
            "({name: member.name, state: member.stateStr, health: member.health}))))",
        ).stdout.splitlines()[-1]
    )
    for member in sorted(status, key=lambda item: item["name"]):
        logger.info(
            "MongoDB member %s: role=%s health=%s",
            member["name"],
            member["state"],
            member["health"],
        )

    assert len(status) == deployment.replica_count
    assert sum(member["state"] == "PRIMARY" for member in status) == 1
    assert sum(member["state"] == "SECONDARY" for member in status) == 2
    assert all(member["health"] == 1 for member in status)

    key_hashes = {
        _kubectl(
            deployment.namespace,
            "exec",
            f"{deployment.release}-mongodb-{ordinal}",
            "--container",
            "mongodb",
            "--",
            "sha256sum",
            "/etc/keyfile/replica-key",
        ).stdout.split()[0]
        for ordinal in range(deployment.replica_count)
    }
    assert len(key_hashes) == 1
    logger.info("All %s MongoDB members use the same replica key", len(status))

    unauthenticated_status = _mongodb_eval(
        deployment.namespace,
        deployment.release,
        "rs.status().ok",
        authenticated=False,
        check=False,
    )
    assert unauthenticated_status.returncode != 0
    assert (
        "requires authentication"
        in (unauthenticated_status.stdout + unauthenticated_status.stderr).lower()
    )
    logger.info("Unauthenticated replica-set status access was rejected as expected")


def test_poller_works_after_authentication_transition(
    authenticated_replica_set, setup_splunk
):
    deployment = authenticated_replica_set
    search = (
        'search index="netops" sourcetype="sc4snmp:event" '
        f'host="{deployment.poll_target}" earliest={deployment.transition_started_at} '
        '"SNMPv2-MIB.sysDescr.value"=* '
        "| head 1"
    )
    result_count, event_count = wait_for_splunk_search(
        setup_splunk,
        search,
        "polling data after the MongoDB authentication transition",
        timeout=300,
    )
    assert result_count > 0
    assert event_count > 0
    logger.info(
        "Polling profile %s produced an event after the transition", POLL_PROFILE
    )


def test_traps_work_after_authentication_transition(
    authenticated_replica_set, setup_splunk
):
    deployment = authenticated_replica_set
    marker = f"mongodb-auth-transition-{time.time_ns()}"
    iterator = sendNotification(
        SnmpEngine(),
        CommunityData("public", mpModel=1),
        UdpTransportTarget((deployment.trap_host, deployment.trap_port)),
        ContextData(),
        "trap",
        NotificationType(ObjectIdentity("1.3.6.1.6.3.1.1.5.1")).addVarBinds(
            ("1.3.6.1.2.1.1.1.0", OctetString(marker))
        ),
    )
    error_indication, error_status, _, _ = next(iterator)
    assert error_indication is None
    assert not error_status

    search = (
        'search index="netops" sourcetype="sc4snmp:traps" '
        f"earliest={deployment.transition_started_at} "
        f'"SNMPv2-MIB.sysDescr.value"="{marker}" | head 1'
    )
    result_count, event_count = wait_for_splunk_search(
        setup_splunk,
        search,
        "a trap sent after the MongoDB authentication transition",
        timeout=180,
    )
    assert result_count == 1
    assert event_count == 1
    logger.info("A test trap was indexed after the transition")
