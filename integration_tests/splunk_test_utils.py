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


inventory_template = """poller:
  inventory: |
    address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
"""

profiles_template = """scheduler:
  profiles: |
"""

groups_template = """scheduler:
  groups: |
"""

poller_secrets_template = """scheduler:
  usernameSecrets:
"""

traps_secrets_template = """traps:
  usernameSecrets:
"""

polling_secrets_template = """poller:
  usernameSecrets:
"""

TEMPLATE_MAPPING = {
    "inventory.yaml": inventory_template,
    "profiles.yaml": profiles_template,
    "scheduler_secrets.yaml": poller_secrets_template,
    "traps_secrets.yaml": traps_secrets_template,
    "polling_secrets.yaml": polling_secrets_template,
    "groups.yaml": groups_template,
}


def l_pad_string(s):
    lines = s.splitlines()
    result = "\n".join(str.rjust(" ", 4) + line for line in lines)
    return result


def yaml_escape_list(*l):
    ret = ruamel.yaml.comments.CommentedSeq(l)
    ret.fa.set_flow_style()
    return ret


def update_file(entries, fieldname):
    result = ""
    for e in entries:
        result += str.rjust(" ", 4) + e + "\n"

    template = TEMPLATE_MAPPING.get(fieldname, "")
    result = template + result
    with open(fieldname, "w") as fp:
        fp.write(result)


def update_profiles(profiles):
    yaml = ruamel.yaml.YAML()
    with open("profiles_tmp.yaml", "w") as fp:
        yaml.dump(profiles, fp)

    with open("profiles.yaml", "w") as fp:
        fp.write(profiles_template)
        with open("profiles_tmp.yaml") as fp2:
            line = fp2.readline()
            while line != "":
                new_line = str.rjust(" ", 4) + line
                fp.write(new_line)
                line = fp2.readline()


def update_groups(groups):
    yaml = ruamel.yaml.YAML()
    with open("groups_tmp.yaml", "w") as fp:
        yaml.dump(groups, fp)

    with open("groups.yaml", "w") as fp:
        fp.write(groups_template)
        with open("groups_tmp.yaml") as fp2:
            line = fp2.readline()
            while line != "":
                new_line = str.rjust(" ", 4) + line
                fp.write(new_line)
                line = fp2.readline()


def upgrade_helm(yaml_files):
    files_string = "-f values.yaml "
    for file in yaml_files:
        files_string += f"-f {file} "
    os.system(
        "sudo microk8s kubectl delete jobs/snmp-splunk-connect-for-snmp-inventory -n sc4snmp"
    )
    os.system(
        f"sudo microk8s helm3 upgrade --install snmp {files_string} ~/splunk-connect-for-snmp/charts/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace"
    )
    # temparorily added
    time.sleep(30)


def create_v3_secrets(
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


def wait_for_pod_initialization():
    script_body = f""" 
    while [ "$(sudo microk8s kubectl get pod -n sc4snmp | grep "worker-trap" | grep Running | wc -l)" != "1" ] ; do
        echo "Waiting for POD initialization..."
        sleep 1
    done """
    with open("check_for_pods.sh", "w") as fp:
        fp.write(script_body)
    os.system("chmod a+x check_for_pods.sh && ./check_for_pods.sh")


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
