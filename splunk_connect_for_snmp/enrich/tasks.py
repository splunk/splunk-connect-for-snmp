try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass

import os
from hashlib import shake_128
from itertools import islice

import pymongo
from bson.objectid import ObjectId
from celery import Task, shared_task
from celery.utils.log import get_task_logger
from pysnmp.proto.api.v2c import Null

from splunk_connect_for_snmp.app import app

logger = get_task_logger(__name__)

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "sc4")


def chunk(it, size):
    it = iter(it)
    return iter(lambda: tuple(islice(it, size)), ())


class EnrichTask(Task):
    def __init__(self):
        pass


TRACKED_F = [
    "SNMPv2-MIB.sysDescr",
    "SNMPv2-MIB.sysObjectID",
    "SNMPv2-MIB.sysContact",
    "SNMPv2-MIB.sysName",
    "SNMPv2-MIB.sysLocation",
]
TRACKED_CC = ["CHECKPOINT-MIB-2.sysUpTime"]


@shared_task(bind=True, base=EnrichTask)
def enrich(self, **kwargs):
    mongo_client = pymongo.MongoClient(MONGO_URI)
    targets_collection = mongo_client.sc4.targets
    updates = []
    result = kwargs["result"]
    target_id = ObjectId(kwargs["id"])
    current_target = targets_collection.find_one(
        {"_id": target_id}, {"attributes": True}
    )
    detectchange: bool = False
    if "detectchange" in kwargs:
        detectchange = True
    reschedule: bool = False
    if "reschedule" in kwargs:
        reschedule = True

    if not "attributes" in current_target:
        current_target["attributes"] = {}

    # TODO: Compare the ts field with the lastmodified time of record and only update if we are newer

    # First write back to DB new/changed data
    for group_key, group_data in result.items():
        group_key_hash = shake_128(group_key.encode()).hexdigest(255)

        if (
            not group_key_hash in current_target["attributes"]
            and len(group_data["fields"]) > 0
        ):

            current_target["attributes"][group_key_hash] = {
                "id": group_key,
                "fields": {},
                "metrics": {},
            }
            updates.append(
                {"$set": {"attributes": {group_key_hash: {"id": group_key}}}}
            )

        for field_key, field_value in group_data["fields"].items():
            field_key_hash = shake_128(field_key.encode()).hexdigest(255)
            field_value["name"] = field_key
            cv = None

            if field_key_hash in current_target["attributes"][group_key_hash]["fields"]:
                cv = current_target["attributes"][group_key_hash]["fields"][
                    field_key_hash
                ]

            if cv and not cv == field_value:
                # modifed

                updates.append(
                    {
                        "$set": {
                            "attributes": {
                                group_key_hash: {
                                    "fields": {field_key_hash: field_value}
                                }
                            }
                        }
                    }
                )

            elif cv:
                # unchanged
                pass
            else:
                # new
                updates.append(
                    {
                        "$set": {
                            "attributes": {
                                group_key_hash: {
                                    "fields": {field_key_hash: field_value}
                                }
                            }
                        }
                    }
                )
            if field_key in TRACKED_F:
                updates.append(
                    {"$set": {"state": {field_key.replace(".", "|"): field_value}}}
                )

            if len(updates) >= 20:
                targets_collection.update_one({"_id": target_id}, updates, upsert=True)
                updates.clear()

        # Now add back any fields we need
        for current_key, current_data in current_target["attributes"].items():
            if current_data["id"] in result:
                for field_key, field_data in result[current_data["id"]][
                    "fields"
                ].items():
                    if not field_key in result[current_data["id"]]["fields"]:
                        logger.debug(
                            f"Using Cached Attribute {field_key}={current_data['value']}"
                        )
                        result[current_data["id"]]["fields"][field_key] = current_data[
                            "value"
                        ]

    app.send_task(
        "splunk_connect_for_snmp.inventory.tasks.inventory_setup_poller",
        kwargs=({"id": kwargs["id"]}),
    )

    return result
