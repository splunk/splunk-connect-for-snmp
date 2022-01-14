#
# Copyright 2021 Splunk Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from splunk_connect_for_snmp import customtaskmanager

try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass

import os
from hashlib import shake_128
from itertools import islice

import pymongo
from celery import Task, shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "sc4snmp")

TRACKED_F = [
    "SNMPv2-MIB.sysDescr",
    "SNMPv2-MIB.sysObjectID",
    "SNMPv2-MIB.sysContact",
    "SNMPv2-MIB.sysName",
    "SNMPv2-MIB.sysLocation",
]

SYS_UP_TIME = "SNMPv2-MIB.sysUpTime"


def chunk(it, size):
    it = iter(it)
    return iter(lambda: tuple(islice(it, size)), ())


# check if sysUpTime decreased, if so trigger new walk
def check_restart(current_target, result, targets_collection, address):
    for group_key, group_dict in result.items():
        if "metrics" in group_dict and SYS_UP_TIME in group_dict["metrics"]:
            sysuptime = group_dict["metrics"][SYS_UP_TIME]
            new_value = sysuptime["value"]

            logger.debug(f"current target = {current_target}")
            if "sysUpTime" in current_target:
                old_value = current_target["sysUpTime"]["value"]
                logger.debug(f"new_value = {new_value}  old_value = {old_value}")
                if int(new_value) < int(old_value):
                    task_config = {
                        "name": f'sc4snmp;{address};walk',
                        "run_immediately": True,
                    }
                    logger.info(
                        f'Detected restart of {address}, triggering walk'
                    )
                    periodic_obj = customtaskmanager.CustomPeriodicTaskManager()
                    periodic_obj.manage_task(**task_config)

            state = {
                "value": sysuptime["value"],
                "type": sysuptime["type"],
                "oid": sysuptime["oid"],
            }

            targets_collection.update_one(
                {"address": address}, {"$set": {"sysUpTime": state}}, upsert=True
            )


class EnrichTask(Task):
    def __init__(self):
        pass


@shared_task(bind=True, base=EnrichTask)
def enrich(self, result):
    address = result["address"]
    mongo_client = pymongo.MongoClient(MONGO_URI)
    targets_collection = mongo_client.sc4snmp.targets
    attributes_collection = mongo_client.sc4snmp.attributes
    updates = []
    attribute_updates = []

    current_target = targets_collection.find_one(
        {"address": address}, {"target": True, "sysUpTime": True}
    )
    if not current_target:
        logger.info(f"First time for {address}")
        current_target = {"address": address}
    else:
        logger.info(f"Not first time for {address}")

    # TODO: Compare the ts field with the lastmodified time of record and only update if we are newer
    check_restart(current_target, result["result"], targets_collection, address)

    # First write back to DB new/changed data
    for group_key, group_data in result["result"].items():
        group_key_hash = shake_128(group_key.encode()).hexdigest(255)

        current_attributes = attributes_collection.find_one(
            {"address": address, "group_key_hash": group_key_hash}, {"fields": True, "id": True})

        if not current_attributes and group_data["fields"]:
            attributes_collection.update_one(
                {"address": address, "group_key_hash": group_key_hash},
                {"$set": {"id": group_key}},
                upsert=True,
            )

        for field_key, field_value in group_data["fields"].items():
            field_key_hash = shake_128(field_key.encode()).hexdigest(255)
            field_value["name"] = field_key
            cv = None

            if current_attributes and field_key_hash in current_attributes.get("fields", {}):
                cv = current_attributes["fields"][field_key_hash]

            if cv and not cv == field_value:
                # modifed
                attribute_updates.append(
                    {
                        "$set": {
                            "fields": {field_key_hash: field_value}
                        }
                    }
                )

            elif cv:
                # unchanged
                pass
            else:
                # new
                attribute_updates.append(
                    {
                        "$set": {
                            "fields": {field_key_hash: field_value}
                        }
                    }
                )
            if field_key in TRACKED_F:
                updates.append(
                    {"$set": {"state": {field_key.replace(".", "|"): field_value}}}
                )

            if len(updates) >= 20:
                targets_collection.update_one(
                    {"address": address}, updates, upsert=True
                )
                updates.clear()
            if len(attribute_updates) >= 20:
                attributes_collection.update_one(
                    {"address": address, "group_key_hash": group_key_hash, "id": group_key}, attribute_updates, upsert=True
                )
                attribute_updates.clear()

        if updates:
            targets_collection.update_one(
                {"address": address}, updates, upsert=True
            )
            updates.clear()
        if attribute_updates:
            attributes_collection.update_one(
                {"address": address, "group_key_hash": group_key_hash, "id": group_key}, attribute_updates, upsert=True
            )
            attribute_updates.clear()

        if len(updates) > 0:
            targets_collection.update_one(
                {"address": address}, updates, upsert=True
            )

        # Now add back any fields we need
        if current_attributes:
            attribute_group_id = current_attributes["id"]
            fields = current_attributes["fields"]
            if attribute_group_id in result["result"]:
                for persist_data in fields.values():
                    if persist_data["name"] not in result["result"][attribute_group_id]["fields"]:
                        result["result"][attribute_group_id]["fields"][
                            persist_data["name"]
                        ] = persist_data

    return result
