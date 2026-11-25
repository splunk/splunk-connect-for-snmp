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


def dump_docker_logs(project=None):
    logger.info("=" * 60)
    logger.info("DOCKER CONTAINER LOGS (Last 60 lines)")
    logger.info("=" * 60)
    try:
        command = ["docker", "ps", "-a", "--format", "{{.Names}}\t{{.Status}}"]
        if project:
            command.extend(["--filter", f"label=com.docker.compose.project={project}"])
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            logger.info(f"Docker container status:\n{result.stdout}")
            for row in result.stdout.splitlines():
                if not row.strip():
                    continue
                container = row.split()[0]
                logger.info(f"Container: {container}")
                try:
                    logs = subprocess.run(
                        ["docker", "logs", "--tail", "60", container],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        timeout=30,
                    )
                    logger.info(logs.stdout)
                    if logs.returncode:
                        logger.warning("Docker container logs are unavailable")
                except (OSError, subprocess.SubprocessError):
                    logger.warning("Docker container logs could not be collected")
        else:
            logger.warning("Docker container status is unavailable")
    except (OSError, subprocess.SubprocessError):
        logger.warning("Docker diagnostic collection could not finish")
    finally:
        logger.info("=" * 60)
        logger.info("END DOCKER CONTAINER LOGS")
        logger.info("=" * 60)


def dump_kubernetes_logs(namespaces=("sc4snmp",)):
    logger.info("=" * 60)
    logger.info("KUBERNETES POD LOGS (Last 50 lines)")
    logger.info("=" * 60)
    try:
        for namespace in namespaces:
            logger.info(f"Namespace: {namespace}")
            result = subprocess.run(
                [
                    "sudo",
                    "microk8s",
                    "kubectl",
                    "get",
                    "pods",
                    "-n",
                    namespace,
                    "--no-headers",
                    "-o",
                    "custom-columns=NAME:.metadata.name,PHASE:.status.phase",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            if result.returncode == 0:
                logger.info(f"Kubernetes pod status:\n{result.stdout}")
                for row in result.stdout.splitlines():
                    if not row.strip():
                        continue
                    pod = row.split()[0]
                    logger.info(f"Pod: {pod}")
                    try:
                        logs = subprocess.run(
                            [
                                "sudo",
                                "microk8s",
                                "kubectl",
                                "logs",
                                "-n",
                                namespace,
                                pod,
                                "--all-containers=true",
                                "--tail=50",
                            ],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True,
                            timeout=30,
                        )
                        logger.info(logs.stdout)
                        if logs.returncode:
                            logger.warning("Kubernetes pod logs are unavailable")
                    except (OSError, subprocess.SubprocessError):
                        logger.warning("Kubernetes pod logs could not be collected")
            else:
                logger.warning("Kubernetes pod status is unavailable")
    except (OSError, subprocess.SubprocessError):
        logger.warning("Kubernetes diagnostic collection could not finish")
    finally:
        logger.info("=" * 60)
        logger.info("END KUBERNETES POD LOGS")
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
def jitter_live(request):
    from integration_tests.utils.polling import LiveJitter

    manifest, target = request.getfixturevalue("jitter_environment")
    if request.node.get_closest_marker("part12"):
        assert target.get("ha") is True, "Failover requires Redis and MongoDB replicas"
    assert target["mode"] == request.config.getoption("sc4snmp_deployment")
    service = request.getfixturevalue("setup_splunk")
    timeout = INTEGRATION_TEST_TIMEOUT
    if request.node.get_closest_marker("long_interval"):
        timeout = max(timeout, 660)
    live = LiveJitter(target, manifest, timeout)
    try:
        live.start_observing()
        yield live
    finally:
        try:
            live.stop_observing()
            if getattr(request.node, "jitter_passed", False) and live.changed:
                from integration_tests.tests.jitter.delivery import (
                    assert_indexed_for_all,
                )

                assert_indexed_for_all(
                    live, service, live.started_at, kinds=("metrics",)
                )
        finally:
            live.stop_events()


@pytest.fixture
def jitter_environment(request, tmp_path_factory):
    from integration_tests.utils import polling_environment as environment
    from integration_tests.utils.files import read_private_json

    target_path = request.config.getoption("jitter_target")
    if target_path:
        from integration_tests.utils.simulators import probe_simulators

        if (
            sum("jitter_live" in item.fixturenames for item in request.session.items)
            != 1
        ):
            raise pytest.UsageError("Select one case when reusing --jitter-target")
        target = read_private_json(target_path)
        manifest = read_private_json(target["manifest_file"])
        # Retained Pods can acquire different endpoints after cluster recovery.
        # Check real SNMP readiness instead of trusting an earlier ready flag.
        asyncio.run(
            probe_simulators(manifest, read_private_json(manifest["credentials_file"]))
        )
        yield manifest, target
        return
    ha = request.node.get_closest_marker("part12") is not None
    if ha and request.config.getoption("sc4snmp_deployment") != "microk8s":
        raise pytest.UsageError(
            "Automatic failover setup requires microk8s. For Docker Compose, "
            "supply --jitter-target for an isolated Redis/Sentinel and MongoDB replica deployment"
        )
    directory = tmp_path_factory.mktemp("jitter-environment-")
    directory.chmod(0o700)
    environment.prepare(
        request.config.getoption("sc4snmp_deployment"),
        directory,
        splunk_test_configuration(request.config),
        ha=ha,
        mongo_inventory=request.node.get_closest_marker("mongo_inventory") is not None,
    )
    target_path = directory / "target.json"
    target = read_private_json(target_path)
    try:
        yield read_private_json(directory / "simulators/endpoints.json"), target
    finally:
        environment.remove_application(target)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_makereport(item, call):
    if "jitter_live" in item.fixturenames and call.when == "call":
        item.jitter_passed = call.excinfo is None
    if call.when != "call":
        return

    if call.excinfo is not None:
        logger.error("\n" + "!" * 60)
        logger.error("TEST FAILED - COLLECTING DEPLOYMENT LOGS")
        logger.error("!" * 60)

        try:
            deployment = item.config.getoption("sc4snmp_deployment")
            target = getattr(item.funcargs.get("jitter_live"), "target", {})

            is_autodiscovery_test = item.get_closest_marker("part8") is not None
            if str(deployment) == "microk8s":
                namespaces = [target.get("namespace", "sc4snmp")]
                if is_autodiscovery_test:
                    namespaces.append("microk8s-agent-simulator")
                dump_kubernetes_logs(namespaces)
            else:
                dump_docker_logs(project=target.get("project"))
                if is_autodiscovery_test:
                    dump_kubernetes_logs(("docker-agent-simulator",))

        except Exception:
            logger.warning("Failure diagnostics could not be collected")
        finally:
            logger.info("=" * 60)
            logger.info("END FAILURE DIAGNOSTICS")
            logger.info("=" * 60)
