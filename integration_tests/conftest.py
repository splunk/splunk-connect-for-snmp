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


def dump_docker_logs():
    containers = [
        "docker_compose-worker-poller-1",
        "docker_compose-worker-sender-1",
        "docker_compose-worker-trap-1",
        "sc4snmp-scheduler",
    ]

    sys.stdout.write("\n" + "=" * 60 + "\n")
    sys.stdout.write("DOCKER ERROR / WARNING LOGS (last 100 lines)\n")
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.flush()

    for container in containers:
        sys.stdout.write(f"\nContainer: {container}\n")
        sys.stdout.write("-" * 60 + "\n")
        sys.stdout.flush()

        # Get last 100 lines and filter ERROR / WARNING
        result = subprocess.run(
            ["docker", "logs", "--tail", "100", container],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )

        for line in result.stdout.splitlines():
            # if "ERROR" in line or "WARNING" in line:
            #     sys.stdout.write(line + "\n"). #test to print all logs
            sys.stdout.write(
                line + "\n"
            )  # test to print all logs git action  latter remove the comment and print only error and warning logs

        sys.stdout.flush()

    sys.stdout.write("\n" + "=" * 60 + "\n")
    sys.stdout.write("END OF ERROR LOGS\n")
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.flush()


def dump_kubernetes_logs():
    """Dump Kubernetes pod logs for debugging failed tests"""
    print("\n" + "=" * 60)
    print("KUBERNETES POD LOGS (Last 50 lines)")
    print("=" * 60)

    try:
        result = subprocess.run(
            ["kubectl", "get", "pods", "-n", "sc4snmp", "-o", "name"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            print(f"Could not get pods: {result.stderr}")
            return

        pod_names = result.stdout.strip().split("\n")

        for pod_name in pod_names:
            if pod_name:
                pod_name = pod_name.replace("pod/", "")
                print(f"\n{'─' * 60}")
                print(f"Pod: {pod_name}")
                print(f"{'─' * 60}")
                subprocess.run(
                    ["kubectl", "logs", "--tail=50", pod_name, "-n", "sc4snmp"],
                    check=False,
                )
    except Exception as e:
        print(f"Error getting K8s logs: {e}")

    print("\n" + "=" * 60)
    print("END OF KUBERNETES LOGS")
    print("=" * 60 + "\n")


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
        sys.stdout.write("\n" + "!" * 60 + "\n")
        sys.stdout.write("TEST FAILED - DUMPING LOGS\n")
        sys.stdout.write("!" * 60 + "\n")
        sys.stdout.flush()

        try:
            deployment = item.config.getoption("sc4snmp_deployment")

            if str(deployment) == "microk8s":
                dump_kubernetes_logs()
            else:
                dump_docker_logs()
        except Exception as e:
            sys.stdout.write(f"Could not determine deployment: {e}\n")
            sys.stdout.flush()
            dump_docker_logs()
