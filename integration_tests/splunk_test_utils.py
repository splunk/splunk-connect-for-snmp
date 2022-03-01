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

import yaml


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
    address,port,version,community,secret,securityEngine,walk_interval,profiles,SmartProfiles,delete
"""

profiles_template = """scheduler:
  profiles: |
"""

traps_secrets_template = """traps:
  usernameSecrets:
"""


def l_pad_string(s):
    lines = s.splitlines()
    result = "\n".join(str.rjust(" ", 4) + line for line in lines)
    return result


def update_traps(entries):
    result = ""
    for e in entries:
        result += str.rjust(" ", 4) + "- " + e + "\n"

    result = inventory_template + result
    with open("traps.yaml", "w") as fp:
        fp.write(result)

    os.system(
        "sudo microk8s helm3 upgrade --install snmp -f traps.yaml ~/splunk-connect-for-snmp/charts/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace"
    )


def update_inventory(entries):
    result = ""
    for e in entries:
        result += str.rjust(" ", 4) + e + "\n"

    result = inventory_template + result
    with open("inventory.yaml", "w") as fp:
        fp.write(result)

    os.system(
        "sudo microk8s helm3 upgrade --install snmp -f inventory.yaml ~/splunk-connect-for-snmp/charts/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace"
    )


def update_profiles(profiles):
    with open("profiles.yaml", "w") as fp:
        result = l_pad_string(yaml.dump(profiles, default_flow_style=None))
        fp.write(profiles_template + result)

    os.system(
        "sudo microk8s helm3 upgrade --install snmp -f profiles.yaml ~/splunk-connect-for-snmp/charts/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace"
    )


def create_v3_secrets():
    os.system(
      "sudo microk8s kubectl create -n sc4snmp secret generic secretv4 \
      --from-literal=userName=snmp-poller \
      --from-literal=authKey=PASSWORD1 \
      --from-literal=privKey=PASSWORD1 \
      --from-literal=authProtocol=SHA \
      --from-literal=privProtocol=AES \
      --from-literal=securityEngineId=8000000903000A397056B8AC")

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
