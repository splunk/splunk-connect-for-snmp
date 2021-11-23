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

logger = get_task_logger(__name__)

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "sc4snmp")


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
TRACKED_CC = ["SNMPv2-MIB.sysUpTime"]


@shared_task(bind=True, base=EnrichTask)
def enrich(self, result):
    mongo_client = pymongo.MongoClient(MONGO_URI)
    targets_collection = mongo_client.sc4snmp.targets
    updates = []
    target_id = ObjectId(result["id"])
    current_target = targets_collection.find_one(
        {"_id": target_id}, {"attributes": True, "target": True}
    )
    if not current_target:
        current_target = {}
    if "attributes" not in current_target:
        current_target["attributes"] = {}

    # TODO: Compare the ts field with the lastmodified time of record and only update if we are newer

    # First write back to DB new/changed data
    for group_key, group_data in result["result"].items():
        group_key_hash = shake_128(group_key.encode()).hexdigest(255)

        if (
            group_key_hash not in current_target["attributes"]
            and len(group_data["fields"]) > 0
        ):

            # current_target["attributes"][group_key_hash] = {
            #     "id": group_key,
            #     "fields": {},
            #     "metrics": {},
            # }
            updates.append(
                {"$set": {"attributes": {group_key_hash: {"id": group_key}}}}
            )

        for field_key, field_value in group_data["fields"].items():
            field_key_hash = shake_128(field_key.encode()).hexdigest(255)
            field_value["name"] = field_key
            cv = None

            if field_key_hash in current_target["attributes"].get(
                group_key_hash, {}
            ).get("fields", {}):
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
        current_group_data = current_target["attributes"].get(group_key_hash, None)
        if current_group_data:
            id = current_group_data["id"]
            fields = current_group_data["fields"]
            if id in result["result"]:
                for persist_data in fields.values():
                    if persist_data["name"] not in result["result"][id]["fields"]:
                        result["result"][id]["fields"][
                            persist_data["name"]
                        ] = persist_data

    result["host"] = current_target["target"].split(":")[0]
    return result
