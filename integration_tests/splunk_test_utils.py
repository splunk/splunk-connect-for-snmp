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
import os
import time

import ruamel


def splunk_single_search(service, search):
    kwargs_normal_search = {"exec_mode": "normal"}
    tried = 0
    while True:
        job = service.jobs.create(search, **kwargs_normal_search)
        while True:
            while not job.is_ready():
                pass
            stats = {
                "isDone": job["isDone"],
                "doneProgress": float(job["doneProgress"]) * 100,
                "scanCount": int(job["scanCount"]),
                "eventCount": int(job["eventCount"]),
                "resultCount": int(job["resultCount"]),
            }

            if stats["isDone"] == "1":
                break
            else:
                time.sleep(2)

        result_count = stats["resultCount"]
        event_count = stats["eventCount"]
        if result_count > 0 or tried > 5:
            break
        else:
            tried += 1
            time.sleep(5)
    return result_count, event_count


inventory_template_compose = """address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
"""

inventory_template_microk8s = """poller:
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
    "profiles.yaml": profiles_template_microk8s,
    "scheduler_secrets.yaml": poller_secrets_template_microk8s,
    "traps_secrets.yaml": traps_secrets_template_microk8s,
    "polling_secrets.yaml": polling_secrets_template_microk8s,
    "groups.yaml": groups_template_microk8s,
}


def l_pad_string(s):
    lines = s.splitlines()
    result = "\n".join(str.rjust(" ", 4) + line for line in lines)
    return result


def yaml_escape_list(*l):
    ret = ruamel.yaml.comments.CommentedSeq(l)
    ret.fa.set_flow_style()
    return ret


def update_inventory_compose(records):
    result = ""
    for r in records:
        result += r + "\n"
    result = inventory_template_compose + result
    with open("inventory-tests.csv", "w") as fp:
        fp.write(result)


def update_profiles_compose(profiles):
    yaml = ruamel.yaml.YAML()
    with open("scheduler-config.yaml") as f_tmp:
        scheduler_config = yaml.load(f_tmp)
    scheduler_config["profiles"] = profiles
    with open("scheduler-config.yaml", "w") as file:
        yaml.dump(scheduler_config, file)


def update_groups_compose(groups):
    yaml = ruamel.yaml.YAML()
    with open("scheduler-config.yaml") as f_tmp:
        scheduler_config = yaml.load(f_tmp)
    scheduler_config["groups"] = groups
    with open("scheduler-config.yaml", "w") as file:
        yaml.dump(scheduler_config, file)


def update_traps_secrets_compose(secrets):
    yaml = ruamel.yaml.YAML()
    with open("traps-config.yaml") as f_tmp:
        traps_config = yaml.load(f_tmp)
    traps_config["usernameSecrets"] = secrets
    with open("traps-config.yaml", "w") as file:
        yaml.dump(traps_config, file)


def upgrade_docker_compose():
    os.system("sudo docker compose up -d")


def create_v3_secrets_compose(
    secret_name="secretv4",
    user_name="snmp-poller",
    auth_key="PASSWORD1",
    priv_key="PASSWORD1",
    auth_protocol="SHA",
    priv_protocol="AES",
):
    os.system(
        f'python3 $(realpath "manage_secrets.py") --path_to_compose $(pwd) \
    --secret_name {secret_name} \
    --userName {user_name} \
    --privProtocol {priv_protocol} \
    --privKey {priv_key} \
    --authProtocol {auth_protocol} \
    --authKey {auth_key} \
    --contextEngineId 8000000903000A397056B8AC'
    )


def wait_for_containers_initialization():
    script_body = """ 
    while true; do
        CONTAINERS_SC4SNMP=$(sudo docker ps | grep "sc4snmp\\|worker-poller\\|worker-sender\\|worker-trap" | grep -v "Name" | wc -l)
        if [ "$CONTAINERS_SC4SNMP" -gt 0 ]; then
          CONTAINERS_UP=$(sudo docker ps | grep "sc4snmp\\|worker-poller\\|worker-sender\\|worker-trap" | grep "Up" | wc -l)
          CONTAINERS_EXITED=$(sudo docker ps | grep "sc4snmp\\|worker-poller\\|worker-sender\\|worker-trap" | grep "Exited" | wc -l)
          CONTAINERS_TOTAL=$CONTAINERS_SC4SNMP

          if [ "$CONTAINERS_UP" -eq "$CONTAINERS_TOTAL" ] || \
             { [ "$CONTAINERS_EXITED" -eq 1 ] && [ "$((CONTAINERS_UP + CONTAINERS_EXITED))" -eq "$CONTAINERS_TOTAL" ]; }; then
            echo $(green "All 'sc4snmp' containers are ready.")
            break
          fi

          echo $(yellow "Waiting for all 'sc4snmp' containers to be ready...")
        else
          echo $(yellow "No 'sc4snmp' containers found. Waiting for them to appear...")
        fi
        sleep 1
    done 
    """
    with open("check_for_containers.sh", "w") as fp:
        fp.write(script_body)
    os.system("chmod a+x check_for_containers.sh && ./check_for_containers.sh")


def update_file_microk8s(entries, fieldname):
    result = ""
    for e in entries:
        result += str.rjust(" ", 4) + e + "\n"

    template = TEMPLATE_MAPPING_MICROK8S.get(fieldname, "")
    result = template + result
    with open(fieldname, "w") as fp:
        fp.write(result)


def update_profiles_microk8s(profiles):
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


def update_groups_microk8s(groups):
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


def upgrade_helm_microk8s(yaml_files):
    files_string = "-f values.yaml "
    for file in yaml_files:
        files_string += f"-f {file} "
    os.system(
        "sudo microk8s kubectl delete jobs/snmp-splunk-connect-for-snmp-inventory -n sc4snmp"
    )
    was_inventory_correctly_deleted()
    os.system(
        f"sudo microk8s helm3 upgrade --install snmp {files_string} ./../charts/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace"
    )
    was_inventory_upgraded()

def was_inventory_upgraded():
    os.system("./is_inventory_upgraded.sh")

def was_inventory_correctly_deleted():
    os.system("./is_inventory_pod_deleted.sh")

def was_data_sent(profile_name):
    os.system("./is_event_sent.sh " + profile_name)


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