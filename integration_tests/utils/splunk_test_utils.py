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
import os
import shutil
import subprocess
import time
from pathlib import Path

import ruamel

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "configs"
SCHEDULER_CONFIG = CONFIG_DIR / "scheduler-config.yaml"
TRAPS_CONFIG = CONFIG_DIR / "traps-config.yaml"
INVENTORY_FILE = CONFIG_DIR / "inventory-tests.csv"
LOCAL_MIB_DIR = BASE_DIR / "mibs"


def splunk_single_search(service, search, timeout=300, max_retries=5):
    """
    Fetch search results from Splunk with improved reliability.

    Args:
        service: Splunk service client
        search: Search query string
        timeout: Maximum time (seconds) to wait for a single search job (default: 300s)
        max_retries: Maximum number of retry attempts (default: 5)

    Returns:
        tuple: (result_count, event_count)
    """
    kwargs_normal_search = {"exec_mode": "normal"}
    tried = 0

    while tried <= max_retries:
        job = None
        try:
            # Create search job
            logger.info(f"Creating search job (attempt {tried + 1}/{max_retries + 1})")
            job = service.jobs.create(search, **kwargs_normal_search)
            job_id = job.sid
            logger.debug(f"Job SID: {job_id}")

            # Wait for job to be ready with timeout
            start_time = time.time()
            while not job.is_ready():
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    raise TimeoutError(f"Job {job_id} not ready after {timeout}s")
                time.sleep(1)  # Fixed: was busy-waiting, now has sleep

            logger.debug(f"Job {job_id} is ready")

            # Poll for job completion
            start_time = time.time()
            while True:
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    raise TimeoutError(
                        f"Job {job_id} did not complete within {timeout}s"
                    )

                # Refresh job stats
                job.refresh()

                stats = {
                    "isDone": job["isDone"],
                    "doneProgress": float(job["doneProgress"]) * 100,
                    "scanCount": int(job["scanCount"]),
                    "eventCount": int(job["eventCount"]),
                    "resultCount": int(job["resultCount"]),
                }

                logger.debug(
                    f"Job {job_id} stats - Done: {stats['isDone']}, "
                    f"Progress: {stats['doneProgress']:.1f}%, "
                    f"Results: {stats['resultCount']}, Events: {stats['eventCount']}"
                )

                # Check if job is complete (isDone should be "1" or similar truthy value)
                if stats["isDone"] in ("1", 1, True):
                    result_count = stats["resultCount"]
                    event_count = stats["eventCount"]

                    logger.info(
                        f"Search completed: {result_count} results, {event_count} events"
                    )

                    # Success - return results
                    return result_count, event_count

                # Wait before polling again
                time.sleep(2)

        except TimeoutError as e:
            logger.warning(f"Timeout on attempt {tried + 1}/{max_retries + 1}: {e}")
            tried += 1
            if tried <= max_retries:
                logger.info(f"Retrying in 5s...")
                time.sleep(5)
            else:
                logger.error(f"Max retries reached after timeout. Search: {search}")
                return 0, 0

        except Exception as e:
            logger.error(f"Search error on attempt {tried + 1}: {e}", exc_info=True)
            tried += 1
            if tried <= max_retries:
                logger.info(f"Retrying in 5s...")
                time.sleep(5)
            else:
                logger.error(f"Max retries reached. Search: {search}")
                return 0, 0

        finally:
            # Always clean up the job
            if job is not None:
                try:
                    job.cancel()
                except Exception as cleanup_error:
                    logger.debug(f"Error canceling job: {cleanup_error}")

    logger.error(f"Search failed after {max_retries + 1} attempts")
    return 0, 0


inventory_template_compose = """address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
"""

inventory_template_microk8s = """poller:
  enableFullWalk: true
  inventory: |
    address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
"""

inventory_template_microk8s_no_walk = """poller:
  enableFullWalk: false
  inventory: |
    address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
"""

profiles_template_microk8s = """scheduler:
  profiles: |
"""

groups_template_microk8s = """scheduler:
  groups: |
"""

poller_secrets_template_microk8s = """scheduler:
  usernameSecrets:
"""

traps_secrets_template_microk8s = """traps:
  usernameSecrets:
"""

polling_secrets_template_microk8s = """poller:
  usernameSecrets:
"""

TEMPLATE_MAPPING_MICROK8S = {
    "inventory.yaml": inventory_template_microk8s,
    "inventory2.yaml": inventory_template_microk8s_no_walk,
    "profiles.yaml": profiles_template_microk8s,
    "scheduler_secrets.yaml": poller_secrets_template_microk8s,
    "traps_secrets.yaml": traps_secrets_template_microk8s,
    "polling_secrets.yaml": polling_secrets_template_microk8s,
    "groups.yaml": groups_template_microk8s,
}


def l_pad_string(s):
    try:
        if not isinstance(s, str):
            raise ValueError("Input must be a string")

        lines = s.splitlines()
        result = "\n".join(" " * 4 + line for line in lines)

        return result

    except Exception as e:
        logger.error(f" l_pad_string failed → {e}", exc_info=True)
        raise


def yaml_escape_list(*l):
    try:
        if not l:
            logger.warning("yaml_escape_list received empty input")

        ret = ruamel.yaml.comments.CommentedSeq(l)
        ret.fa.set_flow_style()

        return ret

    except Exception as e:
        logger.error(f" yaml_escape_list failed → {e}", exc_info=True)
        raise


def update_inventory_compose(records):
    try:
        if not isinstance(records, list):
            raise ValueError("records must be a list")

        if not records:
            logger.warning(" Inventory records list is empty")

        result = inventory_template_compose

        for r in records:
            if not isinstance(r, str):
                logger.warning(f"Skipping invalid record: {r}")
                continue

            result += r + "\n"

        with open(INVENTORY_FILE, "w") as fp:
            fp.write(result)

        logger.info(f"Inventory updated: {INVENTORY_FILE}")
        logger.debug(f"Inventory content:\n{result}")

    except FileNotFoundError:
        logger.error(f"Inventory file path not found: {INVENTORY_FILE}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"update_inventory_compose failed → {e}", exc_info=True)
        raise


def update_profiles_compose(profiles):
    try:
        if not isinstance(profiles, dict):
            raise ValueError("profiles must be a dictionary")

        yaml = ruamel.yaml.YAML()

        with open(SCHEDULER_CONFIG) as f_tmp:
            scheduler_config = yaml.load(f_tmp)

        if scheduler_config is None:
            raise ValueError("scheduler-config.yaml is empty or invalid")

        scheduler_config["profiles"] = profiles

        with open(SCHEDULER_CONFIG, "w") as file:
            yaml.dump(scheduler_config, file)

        logger.info(" Profiles updated successfully")
        logger.debug(f"Profiles: {profiles}")

    except FileNotFoundError:
        logger.error(
            f"scheduler-config.yaml not found: {SCHEDULER_CONFIG}", exc_info=True
        )
        raise
    except Exception as e:
        logger.error(f"update_profiles_compose failed → {e}", exc_info=True)
        raise


def update_groups_compose(groups):
    try:
        if not isinstance(groups, dict):
            raise ValueError("groups must be a dictionary")

        yaml = ruamel.yaml.YAML()

        with open(SCHEDULER_CONFIG) as f_tmp:
            scheduler_config = yaml.load(f_tmp)

        if scheduler_config is None:
            raise ValueError("scheduler-config.yaml is empty or invalid")

        scheduler_config["groups"] = groups

        with open(SCHEDULER_CONFIG, "w") as file:
            yaml.dump(scheduler_config, file)

        logger.info(" Groups updated successfully")
        logger.debug(f"Groups: {groups}")

    except FileNotFoundError:
        logger.error(
            f"scheduler-config.yaml not found: {SCHEDULER_CONFIG}", exc_info=True
        )
        raise
    except Exception as e:
        logger.error(f"update_groups_compose failed → {e}", exc_info=True)
        raise


def upgrade_env_compose(variable, new_value, env_path=None):
    if env_path is None:
        env_path = str(BASE_DIR / "docker_compose" / ".env")
    try:
        if not variable:
            raise ValueError("Variable name cannot be empty")

        logger.info(f"Updating ENV → {variable}={new_value}")

        lines = []
        found = False

        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.strip().startswith(f"{variable}="):
                        lines.append(f"{variable}={new_value}\n")
                        found = True
                    else:
                        lines.append(line)

        if not found:
            lines.append(f"{variable}={new_value}\n")

        with open(env_path, "w") as f:
            f.writelines(lines)

        logger.info(f" ENV updated: {variable}")

    except Exception as e:
        logger.error(f" upgrade_env_compose failed → {variable} → {e}", exc_info=True)
        raise


def update_traps_secrets_compose(secrets):
    yaml = ruamel.yaml.YAML()
    with open(TRAPS_CONFIG) as f_tmp:
        traps_config = yaml.load(f_tmp)
    traps_config["usernameSecrets"] = secrets
    with open(TRAPS_CONFIG, "w") as file:
        yaml.dump(traps_config, file)


def upgrade_docker_compose():
    compose_dir = BASE_DIR / "docker_compose"
    os.system(
        f"sudo docker compose -f {compose_dir}/docker-compose.yaml "
        f"--env-file {compose_dir}/.env up -d --force-recreate"
    )


def rebuild_stack_preserve_mongo_compose():
    """
    Simulate rebuilding the environment from scratch while keeping the MongoDB data
    volume: wipe Redis (RedBeat's schedule store) and recreate the poller/scheduler/worker
    containers, but leave the `mongo` container/volume untouched. Then re-run the inventory
    container the same way a normal redeploy does, WITHOUT changing any config file, so the
    inventory records end up "Unchanged" from Mongo's point of view.
    """
    compose_dir = BASE_DIR / "docker_compose"
    logger.info("Wiping Redis to simulate a rebuild that drops RedBeat's schedule")
    os.system("sudo docker exec redis redis-cli FLUSHALL")
    os.system(
        f"sudo docker compose -f {compose_dir}/docker-compose.yaml "
        f"--env-file {compose_dir}/.env up -d --force-recreate "
        f"redis scheduler worker-poller worker-sender worker-trap"
    )
    logger.info("Re-running inventory container without any config change")
    os.system(
        f"sudo docker compose -f {compose_dir}/docker-compose.yaml "
        f"--env-file {compose_dir}/.env up -d --force-recreate inventory"
    )


def create_v3_secrets_compose():
    upgrade_env_compose("ENABLE_TRAPS_SECRETS", "true")
    upgrade_env_compose(
        "SECRET_FOLDER_PATH",
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "sample_v3_values",
        ),
    )


def _wait_for_docker_container_running(container_name, timeout=120):
    start = time.time()
    while time.time() - start < timeout:
        result = subprocess.run(
            ["sudo", "docker", "inspect", "-f", "{{.State.Running}}", container_name],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout.strip() == "true":
            return
        time.sleep(1)
    logger.warning(
        f"Container {container_name} did not become running within {timeout}s"
    )


def configure_local_mibs_compose():
    """
    Copy the local_mibs test fixture into the docker-compose project's
    local_mibs directory (the default bind-mount target for the mibserver,
    see LOCAL_MIBS_PATH in docker_compose/.env), then recreate the mibserver
    container so it recompiles its vendor MIB directory.
    """
    compose_dir = BASE_DIR / "docker_compose"
    local_mibs_dir = compose_dir / "local_mibs" / "TESTVENDOR"
    local_mibs_dir.mkdir(parents=True, exist_ok=True)

    for mib_file in (LOCAL_MIB_DIR / "TESTVENDOR").iterdir():
        dest = local_mibs_dir / mib_file.name
        shutil.copy(mib_file, dest)
        os.chmod(dest, 0o644)

    logger.info(f"Local MIBs copied to {local_mibs_dir}")

    os.system(
        f"sudo docker compose -f {compose_dir}/docker-compose.yaml "
        f"--env-file {compose_dir}/.env up -d --force-recreate snmp-mibserver"
    )
    _wait_for_docker_container_running("snmp-mibserver")
    time.sleep(10)  # allow the mibserver to finish compiling the local MIBs


def fetch_mib_index_compose():
    """Fetch the mibserver's compiled MIB index from inside the network."""
    result = subprocess.run(
        [
            "sudo",
            "docker",
            "exec",
            "sc4snmp-scheduler",
            "python",
            "-c",
            "import urllib.request;"
            "print(urllib.request.urlopen("
            "'http://snmp-mibserver:8000/index.csv').read().decode())",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        logger.error(f"Failed to fetch mibserver index: {result.stderr}")
    return result.stdout


def get_mibserver_logs_compose(tail_lines=200):
    result = subprocess.run(
        ["sudo", "docker", "logs", "--tail", str(tail_lines), "snmp-mibserver"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout + result.stderr


def wait_for_containers_initialization():
    script_body = """#!/bin/bash
    while true; do
        CONTAINERS_SC4SNMP=$(sudo docker ps | grep "sc4snmp\\|worker-poller\\|worker-sender\\|worker-trap" | grep -v "Name" | wc -l)
        if [ "$CONTAINERS_SC4SNMP" -gt 0 ]; then
        CONTAINERS_UP=$(sudo docker ps | grep "sc4snmp\\|worker-poller\\|worker-sender\\|worker-trap" | grep "Up" | wc -l)
        CONTAINERS_EXITED=$(sudo docker ps | grep "sc4snmp\\|worker-poller\\|worker-sender\\|worker-trap" | grep "Exited" | wc -l)
        CONTAINERS_TOTAL=$CONTAINERS_SC4SNMP
        if [ "$CONTAINERS_UP" -eq "$CONTAINERS_TOTAL" ] || \\
            { [ "$CONTAINERS_EXITED" -eq 1 ] && [ "$((CONTAINERS_UP + CONTAINERS_EXITED))" -eq "$CONTAINERS_TOTAL" ]; }; then
            echo "All 'sc4snmp' containers are ready."
            break
        fi
        echo "Waiting for all 'sc4snmp' containers to be ready..."
        else
        echo "No 'sc4snmp' containers found. Waiting for them to appear..."
        fi
        sleep 1
    done
    """
    with open("check_for_containers.sh", "w") as fp:
        fp.write(script_body)
    os.system("chmod a+x check_for_containers.sh && ./check_for_containers.sh")


def update_file_microk8s(entries, fieldname):
    try:
        result = ""
        for e in entries:
            result += str.rjust(" ", 4) + e + "\n"

        template = TEMPLATE_MAPPING_MICROK8S.get(fieldname, "")
        result = template + result
        with open(fieldname, "w") as fp:
            fp.write(result)

    except Exception as e:
        logger.error(f"[ERROR] Failed to update file '{fieldname}': {e}")
        raise


def update_profiles_microk8s(profiles):
    try:

        yaml = ruamel.yaml.YAML()
        with open("profiles_tmp.yaml", "w") as fp:
            yaml.dump(profiles, fp)

        with open("profiles.yaml", "w") as fp:
            fp.write(profiles_template_microk8s)
            with open("profiles_tmp.yaml") as fp2:
                line = fp2.readline()
                while line != "":
                    new_line = str.rjust(" ", 4) + line
                    fp.write(new_line)
                    line = fp2.readline()

    except Exception as e:
        logger.info(f"[ERROR] Failed to update profiles: {e}")
        raise


def update_groups_microk8s(groups):
    try:
        yaml = ruamel.yaml.YAML()
        with open("groups_tmp.yaml", "w") as fp:
            yaml.dump(groups, fp)

        with open("groups.yaml", "w") as fp:
            fp.write(groups_template_microk8s)
            with open("groups_tmp.yaml") as fp2:
                line = fp2.readline()
                while line != "":
                    new_line = str.rjust(" ", 4) + line
                    fp.write(new_line)
                    line = fp2.readline()

    except Exception as e:
        logger.info(f"[ERROR] Failed to update groups: {e}")
        raise


def upgrade_helm_microk8s(yaml_files):
    try:
        files_string = "-f values.yaml "
        for file in yaml_files:
            files_string += f"-f {file} "
        os.system(
            "sudo microk8s kubectl delete jobs/snmp-splunk-connect-for-snmp-inventory -n sc4snmp"
        )
        os.system(
            f"sudo microk8s helm3 upgrade --install snmp {files_string} ./../charts/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace"
        )

    except Exception as e:
        logger.info(f"[ERROR] Helm upgrade failed: {e}")
        raise


def rebuild_stack_preserve_mongo_microk8s():
    """
    Simulate rebuilding the environment from scratch while keeping the MongoDB PVC: delete
    the Redis StatefulSet (RedBeat's schedule store) and the scheduler/worker Deployments,
    but never touch the `snmp-mongodb` StatefulSet or its PVC. `helm upgrade` recreates the
    deleted resources on re-apply. Finally re-run the inventory Job WITHOUT changing any
    `-f` values file, so the inventory records end up "Unchanged" from Mongo's point of view.
    """
    try:
        logger.info(
            "Deleting Redis/scheduler/worker resources to simulate a rebuild "
            "that drops RedBeat's schedule, while keeping the Mongo PVC"
        )
        os.system(
            "sudo microk8s kubectl delete statefulset snmp-redis-standalone -n sc4snmp"
        )
        os.system(
            "sudo microk8s kubectl delete deployment "
            "snmp-splunk-connect-for-snmp-scheduler "
            "snmp-splunk-connect-for-snmp-worker-poller "
            "snmp-splunk-connect-for-snmp-worker-sender "
            "snmp-splunk-connect-for-snmp-worker-trap "
            "-n sc4snmp --ignore-not-found"
        )
        os.system(
            "sudo microk8s kubectl delete jobs/snmp-splunk-connect-for-snmp-inventory -n sc4snmp"
        )
        logger.info("Re-installing the release without any config change")
        os.system(
            "sudo microk8s helm3 upgrade --install snmp -f values.yaml "
            "./../charts/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace"
        )

    except Exception as e:
        logger.info(f"[ERROR] Rebuild simulation failed: {e}")
        raise


def create_v3_secrets_microk8s(
    secret_name="secretv4",
    user_name="snmp-poller",
    auth_key="PASSWORD1",
    priv_key="PASSWORD1",
    auth_protocol="SHA",
    priv_protocol="AES",
):
    os.system(
        f"sudo microk8s kubectl create -n sc4snmp secret generic {secret_name} \
      --from-literal=userName={user_name} \
      --from-literal=authKey={auth_key} \
      --from-literal=privKey={priv_key} \
      --from-literal=authProtocol={auth_protocol} \
      --from-literal=privProtocol={priv_protocol} \
      --from-literal=securityEngineId=8000000903000A397056B8AC"
    )


def wait_for_pod_initialization_microk8s():
    script_body = f"""
    while [ "$(sudo microk8s kubectl get pod -n sc4snmp | grep "worker-trap" | grep Running | wc -l)" != "1" ] ; do
        echo "Waiting for POD initialization..."
        sleep 1
    done """
    with open("check_for_pods.sh", "w") as fp:
        fp.write(script_body)
    os.system("chmod a+x check_for_pods.sh && ./check_for_pods.sh")


LOCAL_MIBS_HOST_PATH_MICROK8S = "/tmp/sc4snmp_local_mibs"

local_mibs_template_microk8s = """mibserver:
  localMibs:
    pathToMibs: "{path}"
"""


def configure_local_mibs_microk8s(host_path=LOCAL_MIBS_HOST_PATH_MICROK8S):
    """
    Copy the local_mibs test fixture to a hostPath directory, make it
    world-readable (the mibserver container runs as a non-root UID/GID and
    hostPath volumes are not chowned by fsGroup, so this is the correct,
    permission-safe setup), write a values fragment pointing
    mibserver.localMibs.pathToMibs at it, upgrade the release, and roll out
    the mibserver deployment so it recompiles the vendor MIB directory.
    """
    vendor_dir = Path(host_path) / "TESTVENDOR"
    vendor_dir.mkdir(parents=True, exist_ok=True)

    for mib_file in (LOCAL_MIB_DIR / "TESTVENDOR").iterdir():
        dest = vendor_dir / mib_file.name
        shutil.copy(mib_file, dest)

    os.system(f"chmod -R a+rX {host_path}")
    logger.info(f"Local MIBs copied to {vendor_dir}")

    with open("local_mibs.yaml", "w") as fp:
        fp.write(local_mibs_template_microk8s.format(path=host_path))

    upgrade_helm_microk8s(["local_mibs.yaml"])
    os.system(
        "sudo microk8s kubectl rollout restart deployment snmp-mibserver -n sc4snmp"
    )
    os.system(
        "sudo microk8s kubectl rollout status deployment snmp-mibserver "
        "-n sc4snmp --timeout=120s"
    )
    time.sleep(10)  # allow the mibserver to finish compiling the local MIBs


def fetch_mib_index_microk8s():
    """Fetch the mibserver's compiled MIB index from inside the cluster."""
    result = subprocess.run(
        [
            "sudo",
            "microk8s",
            "kubectl",
            "exec",
            "deploy/snmp-splunk-connect-for-snmp-scheduler",
            "-n",
            "sc4snmp",
            "--",
            "python",
            "-c",
            "import urllib.request;"
            "print(urllib.request.urlopen("
            "'http://snmp-mibserver:8000/index.csv').read().decode())",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        logger.error(f"Failed to fetch mibserver index: {result.stderr}")
    return result.stdout


def get_mibserver_logs_microk8s(tail_lines=200):
    result = subprocess.run(
        [
            "sudo",
            "microk8s",
            "kubectl",
            "logs",
            "deployment/snmp-mibserver",
            "-n",
            "sc4snmp",
            f"--tail={tail_lines}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout + result.stderr


# if __name__ == "__main__":
#     update_inventory(['192.168.0.1,,2c,public,,,600,,,',
#                       '192.168.0.2,,2c,public,,,602,,,'])
#
#     active_profiles = {
#         "test_2": {
#             "frequency": 120,
#             "varBinds": [
#                 ["IF-MIB", "ifInDiscards", 1],
#                 ["IF-MIB", "ifOutErrors"],
#                 ["SNMPv2-MIB", "sysDescr", 0],
#             ],
#         },
#         "new_profiles": {"frequency": 6, "varBinds": [["IP-MIB"]]},
#         "generic_switch": {
#             "frequency": 5,
#             "varBinds": [
#                 ["SNMPv2-MIB", "sysDescr"],
#                 ["SNMPv2-MIB", "sysName", 0],
#                 ["IF-MIB"],
#                 ["TCP-MIB"],
#                 ["UDP-MIB"],
#             ],
#         },
#     }
#
#     update_profiles(active_profiles)
