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

import json
import logging
import os
import sys
from csv import DictReader

import pymongo
from celery import Task, shared_task
from celery.canvas import chain, group, signature

from splunk_connect_for_snmp import customtaskmanager
from splunk_connect_for_snmp.common.hummanbool import human_bool
from splunk_connect_for_snmp.common.inventory_record import (
    InventoryRecord,
    InventoryRecordEncoder,
)

log_level = "DEBUG"
log_format = logging.Formatter("[%(asctime)s] [%(levelname)s] - %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(log_level)

# writing to stdout
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(log_level)
handler.setFormatter(log_format)
logger.addHandler(handler)

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "sc4snmp")
CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.yaml")
INVENTORY_PATH = os.getenv("INVENTORY_PATH", "/app/inventory/inventory.csv")


def gen_walk_task(ir: InventoryRecord):
    return {
        "name": f"sc4snmp;{ir.address};walk",
        "task": "splunk_connect_for_snmp.snmp.tasks.walk",
        "target": f"{ir.address}",
        "args": [],
        "kwargs": {
            "address": ir.address,
        },
        "options": {
            "link": chain(
                signature("splunk_connect_for_snmp.enrich.tasks.enrich"),
                group(
                    signature(
                        "splunk_connect_for_snmp.inventory.tasks.inventory_setup_poller"
                    ),
                    chain(
                        signature("splunk_connect_for_snmp.splunk.tasks.prepare"),
                        signature("splunk_connect_for_snmp.splunk.tasks.send"),
                    ),
                ),
            ),
        },
        "interval": {"every": ir.walk_interval, "period": "seconds"},
        "enabled": True,
        "run_immediately": True,
    }


def load():
    path = INVENTORY_PATH
    inventory_errors = False
    mongo_client = pymongo.MongoClient(MONGO_URI)
    targets_collection = mongo_client.sc4snmp.targets
    mongo_db = mongo_client[MONGO_DB]
    inventory_records = mongo_db.inventory

    periodic_obj = customtaskmanager.CustomPeriodicTaskManager()

    logger.info(f"Loading inventory from {path}")
    with open(path) as csv_file:
        # Dict reader will trust the header of the csv
        ir_reader = DictReader(csv_file)
        for source_record in ir_reader:
            address = source_record["address"]
            if address.startswith("#"):
                logger.warning(f"Record: {address} is commented out. Skipping...")
                continue
            try:
                ir = InventoryRecord(**source_record)
                if ir.delete:
                    periodic_obj.delete_task(ir.address)
                    inventory_records.delete_one({"address": ir.address})
                    targets_collection.remove({"address": ir.address})
                    logger.info(f"Deleting record: {address}")
                else:
                    status = inventory_records.update_one(
                        {"address": ir.address},
                        {"$set": ir.asdict()},
                        upsert=True,
                    )
                    if status.matched_count == 0:
                        logger.info(f"New Record {ir} {status.upserted_id}")
                    elif status.modified_count == 1 and status.upserted_id is None:
                        logger.info(f"Modified Record {ir}")
                    else:
                        logger.debug(f"Unchanged Record {ir}")
                        continue

                    task_config = gen_walk_task(ir)
                    periodic_obj.manage_task(**task_config)

            except Exception as e:
                inventory_errors = True
                logger.exception(f"Exception raised for {address}: {e}")

    return inventory_errors


if __name__ == "__main__":
    r = load()
    if r:
        sys.exit(1)
