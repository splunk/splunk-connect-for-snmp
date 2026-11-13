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
import subprocess
import time

import pytest
import splunklib.client as client

from integration_tests.utils.deployment import INTEGRATION_TEST_TIMEOUT
from integration_tests.utils.splunk_test_utils import splunk_test_configuration

logger = logging.getLogger(__name__)


def dump_all_docker_logs(tail_lines: int = 60):
    """Dump last N lines from all running Docker containers"""
    logger.info("=" * 60)
    logger.info("DOCKER LOGS (last %s lines)", tail_lines)
    logger.info("=" * 60)

    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    containers = result.stdout.splitlines()

    if not containers:
        logger.info("No running containers found")
        return

    for container in containers:
        logger.info("\nContainer: %s", container)
        logger.info("--" * 60)

        logs = subprocess.run(
            ["docker", "logs", "--tail", str(tail_lines), container],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )

        if logs.stdout:
            for line in logs.stdout.splitlines():
                logger.info(line)
        else:
            logger.info("No logs available")

    logger.info("=" * 60)
    logger.info("END OF DOCKER LOGS")
    logger.info("=" * 60)


def dump_kubernetes_logs(namespaces=("sc4snmp",)):
    logger.info("=" * 60)
    logger.info("KUBERNETES POD LOGS (Last 50 lines)")
    logger.info("=" * 60)

    try:
        for namespace in namespaces:
            result = subprocess.run(
                [
                    "sudo",
                    "microk8s",
                    "kubectl",
                    "get",
                    "pods",
                    "-n",
                    namespace,
                    "-o",
                    "name",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                logger.error("Could not get pods from %s: %s", namespace, result.stderr)
                continue

            pod_names = result.stdout.strip().split("\n")

            for pod_name in pod_names:
                if pod_name:
                    pod_name = pod_name.replace("pod/", "")
                    logger.info("-" * 60)
                    logger.info("Pod: %s/%s", namespace, pod_name)
                    logger.info("-" * 60)

                    logs = subprocess.run(
                        [
                            "sudo",
                            "microk8s",
                            "kubectl",
                            "logs",
                            "--tail=50",
                            pod_name,
                            "-n",
                            namespace,
                        ],
                        capture_output=True,
                        text=True,
                        check=False,
                    )

                    if logs.stdout:
                        logger.info("\n%s", logs.stdout)
                    else:
                        logger.info("No logs for pod %s/%s", namespace, pod_name)

    except Exception as e:
        logger.exception("Error getting K8s logs: %s", e)

    logger.info("=" * 60)
    logger.info("END OF KUBERNETES LOGS")
    logger.info("=" * 60)


def pytest_addoption(parser):
    parser.addoption("--jitter-target", action="store")
    parser.addoption(
        "--splunk_host",
        action="store",
        dest="splunk_host",
        default="127.0.0.1",
        help="Address of the Splunk Server",
    )
    parser.addoption(
        "--trap_external_ip",
        action="store",
        dest="trap_external_ip",
        default="127.0.0.1",
        help="Trap Kubernets external IP",
    )
    parser.addoption(
        "--splunk_port",
        action="store",
        dest="splunk_port",
        default="8089",
        help="Splunk rest port",
    )
    parser.addoption(
        "--splunk_user",
        action="store",
        dest="splunk_user",
        default="admin",
        help="Splunk login user",
    )
    parser.addoption(
        "--splunk_password",
        action="store",
        dest="splunk_password",
        default="12345678",
        help="Splunk password",
    )
    parser.addoption(
        "--sc4snmp_deployment",
        action="store",
        dest="sc4snmp_deployment",
        default="microk8s",
        help="sc4snmp deployment",
    )


@pytest.fixture(scope="session")
def setup_splunk(request):
    config = splunk_test_configuration(request.config)
    connection = {
        "username": config["username"],
        "password": config["password"],
        "host": config["host"],
        "port": config["port"],
    }
    for option in ("verify", "timeout"):
        if option in config:
            connection[option] = config[option]
    tried = 0
    while True:
        try:
            service = client.connect(**connection)
            break
        except ConnectionRefusedError:
            logger.error("Connection error!")
            tried += 1
            if tried > 600:
                raise
            time.sleep(1)
    return service


@pytest.fixture
def jitter_live(request, tmp_path_factory):
    from integration_tests.utils.polling import LiveJitter

    ha_test = request.node.get_closest_marker("part12") is not None
    if ha_test:
        from integration_tests.utils.files import read_private_json

        target_path = request.config.getoption("jitter_target")
        if not target_path:
            pytest.skip("An isolated replica target is required for failover")
        if read_private_json(target_path).get("ha") is not True:
            pytest.skip("The isolated target does not use Redis and MongoDB replicas")
    service = request.getfixturevalue("setup_splunk")
    manifest, target = request.getfixturevalue("jitter_environment")
    assert manifest.get("ready") is True, "Every simulator must pass SNMP readiness"
    assert target["mode"] == request.config.getoption("sc4snmp_deployment")
    directory = tmp_path_factory.mktemp("jitter-evidence-")
    os.chmod(directory, 0o700)
    timeout = INTEGRATION_TEST_TIMEOUT
    if request.node.get_closest_marker("part10"):
        timeout = max(timeout, 660)
    live = LiveJitter(target, manifest, directory, timeout)
    try:
        live.start_observing()
        yield live
    finally:
        # A failed drain retains unresolved delivery state for investigation.
        try:
            live.stop_observing()
            outcome = getattr(request.node, "jitter_outcome", "failed")
            if outcome == "failed":
                live.stop_producers()
            elif live.changed:
                from integration_tests.tests.jitter.delivery import (
                    assert_indexed_for_all,
                )

                # Every successful case must deliver real SNMP metrics. Tests
                # with string-only profiles separately check event output too.
                if outcome == "passed":
                    assert_indexed_for_all(
                        live, service, live.started_at, kinds=("metrics",)
                    )
                live.finish()
        except BaseException:
            # Observer or delivery failures must also stop new scheduled work.
            live.stop_producers()
            raise
        finally:
            live.stop_events()


@pytest.fixture(scope="session")
def jitter_environment(request, tmp_path_factory):
    from integration_tests.utils import polling_environment as environment
    from integration_tests.utils.files import read_private_json

    target_path = request.config.getoption("jitter_target")
    if target_path:
        from integration_tests.utils.simulators import probe_simulators

        target = read_private_json(target_path)
        manifest = read_private_json(target["manifest_file"])
        # Retained Pods can acquire different endpoints after cluster recovery.
        # Check real SNMP readiness instead of trusting an earlier ready flag.
        asyncio.run(
            probe_simulators(manifest, read_private_json(manifest["credentials_file"]))
        )
        yield manifest, target
        return
    directory = tmp_path_factory.mktemp("jitter-environment-")
    directory.chmod(0o700)
    environment.prepare(
        request.config.getoption("sc4snmp_deployment"),
        directory,
        splunk_test_configuration(request.config),
    )
    target_path = directory / "target.json"
    yield read_private_json(directory / "simulators/endpoints.json"), read_private_json(
        target_path
    )
    # Keep failed delivery state and storage available for investigation.
    if request.session.testsfailed == 0:
        environment.cleanup(target_path)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_makereport(item, call):
    """Auto dump logs when any test fails"""
    if any(item.get_closest_marker(f"part{part}") for part in (9, 10, 11, 12)):
        if call.when == "call":
            item.jitter_outcome = "passed"
            if call.excinfo is not None:
                item.jitter_outcome = (
                    "skipped"
                    if call.excinfo.errisinstance(pytest.skip.Exception)
                    else "failed"
                )
        # Jitter evidence stays in its protected run directory. Broad container
        # logs can contain unrelated credentials and device addresses.
        return
    if call.when != "call":
        return

    if call.excinfo is not None:
        logger.error("\n" + "!" * 60)
        logger.error("TEST FAILED - DUMPING LOGS")
        logger.error("!" * 60)

        try:
            deployment = item.config.getoption("sc4snmp_deployment")

            is_autodiscovery_test = item.get_closest_marker("part8") is not None
            if str(deployment) == "microk8s":
                namespaces = ["sc4snmp"]
                if is_autodiscovery_test:
                    namespaces.append("microk8s-agent-simulator")
                dump_kubernetes_logs(namespaces)
            else:
                dump_all_docker_logs()
                if is_autodiscovery_test:
                    dump_kubernetes_logs(("docker-agent-simulator",))

        except Exception as e:
            logger.exception("Could not determine deployment: %s", e)
            dump_all_docker_logs()
