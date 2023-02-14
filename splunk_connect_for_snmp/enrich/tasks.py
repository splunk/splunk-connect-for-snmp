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
import time

from pymongo import UpdateOne

from splunk_connect_for_snmp import customtaskmanager

try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass

import os

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

MONGO_UPDATE_BATCH_THRESHOLD = 20


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
                        "name": f"sc4snmp;{address};walk",
                        "run_immediately": True,
                    }
                    logger.info(f"Detected restart of {address}, triggering walk")
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
    attributes_bulk_write_operations = []
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
    logger.info(f"After check_restart for {address}")
    # First write back to DB new/changed data

    is_any_address_in_attributes_collection = attributes_collection.find_one(
        {"address": address},
    )

    for group_key, group_data in result["result"].items():
        group_key_hash = group_key.replace(".", "|")

        if is_any_address_in_attributes_collection:
            current_attributes = attributes_collection.find_one(
                {"address": address, "group_key_hash": group_key_hash},
                {"fields": True, "id": True},
            )
        else:
            current_attributes = None

        if not current_attributes and group_data["fields"]:
            attributes_collection.update_one(
                {"address": address, "group_key_hash": group_key_hash},
                {"$set": {"id": group_key, "fields": {}}},
                upsert=True,
            )
        new_fields = []
        for field_key, field_value in group_data["fields"].items():
            field_key_hash = field_key.replace(".", "|")
            field_value["name"] = field_key
            cv = None
            if current_attributes and field_key_hash in current_attributes.get(
                "fields", {}
            ):
                cv = current_attributes["fields"][field_key_hash]

            # if new field_value is different than the previous one, update
            if cv and not cv == field_value:
                # modifed
                attribute_updates.append(
                    {"$set": {f"fields.{field_key_hash}": field_value}}
                )

            elif cv:
                # unchanged
                pass
            else:
                # new
                new_fields.append({"$set": {f"fields.{field_key_hash}": field_value}})
            if field_key in TRACKED_F:
                updates.append(
                    {"$set": {f"state.{field_key.replace('.', '|')}": field_value}}
                )

            if len(updates) >= MONGO_UPDATE_BATCH_THRESHOLD:
                targets_collection.update_one(
                    {"address": address}, updates, upsert=True
                )
                updates.clear()

            if len(attribute_updates) >= MONGO_UPDATE_BATCH_THRESHOLD:
                attributes_collection.update_one(
                    {"address": address, "group_key_hash": group_key_hash},
                    attribute_updates,
                    upsert=True,
                )
                attribute_updates.clear()
        if new_fields:
            attributes_bulk_write_operations.append(
                UpdateOne(
                    {"address": address, "group_key_hash": group_key_hash},
                    new_fields.copy(),
                    upsert=True,
                )
            )
            new_fields.clear()

        if updates:
            targets_collection.update_one({"address": address}, updates, upsert=True)
            updates.clear()
        if attribute_updates:
            attributes_collection.update_one(
                {"address": address, "group_key_hash": group_key_hash},
                attribute_updates,
            )
            attribute_updates.clear()

        # Now add back any fields we need
        if current_attributes:
            attribute_group_id = current_attributes["id"]
            fields = current_attributes.get("fields", {})
            if attribute_group_id in result["result"]:
                snmp_object = result["result"][attribute_group_id]
                enrich_metric_with_fields_from_db(snmp_object, fields)
    if attributes_bulk_write_operations:
        logger.debug("Start of bulk_write")
        start = time.time()
        bulk_result = attributes_collection.bulk_write(
            attributes_bulk_write_operations, ordered=False
        )
        end = time.time()
        logger.debug(
            f"ELAPSED TIME OF BULK: {end - start} for {len(attributes_bulk_write_operations)} operations"
        )
        logger.debug(f"result api: {bulk_result.bulk_api_result}")
    return result


def enrich_metric_with_fields_from_db(snmp_object, fields_from_db):
    metrics = snmp_object.get("metrics", {})
    # We don't want to enrich SNMP objects that doesn't contain any metrics
    if not metrics:
        return
    for persist_data in fields_from_db.values():
        if persist_data["name"] not in snmp_object["fields"]:
            snmp_object["fields"][persist_data["name"]] = persist_data
