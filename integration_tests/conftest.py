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
import subprocess
import sys
import time

import pytest
import splunklib.client as client

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
        logger.info("")
        logger.info("Container: %s", container)
        logger.info("-" * 60)

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


def dump_kubernetes_logs():
    logger.info("=" * 60)
    logger.info("KUBERNETES POD LOGS (Last 50 lines)")
    logger.info("=" * 60)

    try:
        result = subprocess.run(
            [
                "sudo",
                "microk8s",
                "kubectl",
                "get",
                "pods",
                "-n",
                "sc4snmp",
                "-o",
                "name",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            logger.error("Could not get pods: %s", result.stderr)
            return

        pod_names = result.stdout.strip().split("\n")

        for pod_name in pod_names:
            if pod_name:
                pod_name = pod_name.replace("pod/", "")
                logger.info("-" * 60)
                logger.info("Pod: %s", pod_name)
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
                        "sc4snmp",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if logs.stdout:
                    logger.info("\n%s", logs.stdout)
                else:
                    logger.info("No logs for pod %s", pod_name)

    except Exception as e:
        logger.exception("Error getting K8s logs: %s", e)

    logger.info("=" * 60)
    logger.info("END OF KUBERNETES LOGS")
    logger.info("=" * 60)


def pytest_addoption(parser):
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
    tried = 0
    while True:
        try:
            username = request.config.getoption("splunk_user")
            password = request.config.getoption("splunk_password")
            hostname = request.config.getoption("splunk_host")
            port = request.config.getoption("splunk_port")
            service = client.connect(
                username=username, password=password, host=hostname, port=port
            )
            break
        except ConnectionRefusedError:
            logger.error("Connection error!")
            tried += 1
            if tried > 600:
                raise
            time.sleep(1)
    return service


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_makereport(item, call):
    """Auto dump logs when any test fails"""
    if call.when != "call":
        return

    if call.excinfo is not None:
        logger.error("\n" + "!" * 60)
        logger.error("TEST FAILED - DUMPING LOGS")
        logger.error("!" * 60)

        try:
            deployment = item.config.getoption("sc4snmp_deployment")

            if str(deployment) == "microk8s":
                dump_kubernetes_logs()
            else:
                dump_all_docker_logs()

        except Exception as e:
            logger.exception("Could not determine deployment: %s", e)
            dump_all_docker_logs()
