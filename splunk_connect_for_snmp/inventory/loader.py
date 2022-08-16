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

import logging
import os
import sys
from csv import DictReader
from copy import copy

import pymongo
import yaml

from splunk_connect_for_snmp import customtaskmanager
from splunk_connect_for_snmp.common.customised_json_formatter import (
    CustomisedJSONFormatter,
)
from splunk_connect_for_snmp.common.inventory_record import InventoryRecord
from splunk_connect_for_snmp.common.profiles import ProfilesManager
from splunk_connect_for_snmp.common.schema_migration import migrate_database
from splunk_connect_for_snmp.common.task_generator import WalkTaskGenerator
from splunk_connect_for_snmp.common.groups import get_group

from ..poller import app

try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass

formatter = CustomisedJSONFormatter()

log_level = "DEBUG"
logger = logging.getLogger(__name__)
logger.setLevel(log_level)

# writing to stdout
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(log_level)
handler.setFormatter(formatter)
logger.addHandler(handler)

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "sc4snmp")
CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.yaml")
INVENTORY_PATH = os.getenv("INVENTORY_PATH", "/app/inventory/inventory.csv")


def transform_address_to_key(address, port):
    if int(port) == 161:
        return address
    else:
        return f"{address}:{port}"


def gen_walk_task(ir: InventoryRecord, profile=None):
    target = transform_address_to_key(ir.address, ir.port)
    walk_definition = WalkTaskGenerator(
        target=target, schedule_period=ir.walk_interval, app=app, profile=profile
    )
    task_config = walk_definition.generate_task_definition()
    return task_config


def load():
    path = INVENTORY_PATH
    inventory_errors = False
    mongo_client = pymongo.MongoClient(MONGO_URI)
    targets_collection = mongo_client.sc4snmp.targets
    attributes_collection = mongo_client.sc4snmp.attributes
    profiles_manager = ProfilesManager(mongo_client)
    mongo_db = mongo_client[MONGO_DB]
    inventory_records = mongo_db.inventory

    periodic_obj = customtaskmanager.CustomPeriodicTaskManager()

    migrate_database(mongo_client, periodic_obj)
    profiles_manager.update_all_profiles()
    config_profiles = profiles_manager.return_all_profiles()

    logger.info(f"Loading inventory from {path}")
    with open(path, encoding="utf-8") as csv_file:
        # Dict reader will trust the header of the csv
        ir_reader = DictReader(csv_file)
        for source_record in ir_reader:
            address = source_record["address"]
            records_converted = []
            if address.startswith("#"):
                logger.warning(f"Record: {address} is commented out. Skipping...")
                continue
            elif address.startswith(('1','2','3','4','5','6','7','8','9','0')):
                records_converted.append(source_record)
            else:
                group_addresses = get_group(address)
                for gr_addr in group_addresses:
                    new_record = copy(source_record)
                    new_record["address"] = gr_addr["ip"]
                    new_record["port"] = gr_addr["port"]
                    records_converted.append(new_record)
            for new_source_record in records_converted:
                try:
                    ir = InventoryRecord(**new_source_record)
                    target = transform_address_to_key(ir.address, ir.port)
                    if ir.delete:
                        periodic_obj.delete_all_tasks_of_host(target)
                        inventory_records.delete_one(
                            {"address": ir.address, "port": ir.port}
                        )
                        targets_collection.remove({"address": target})
                        attributes_collection.remove({"address": target})
                        logger.info(f"Deleting record: {target}")
                    else:
                        profiles = new_source_record["profiles"].split(";")
                        profile = None
                        if profiles:
                            profiles = [
                                p
                                for p in profiles
                                if config_profiles.get(p, {})
                                .get("condition", {})
                                .get("type")
                                == "walk"
                            ]
                            if profiles:
                                profile = profiles[-1]
                                ir.walk_interval = int(new_source_record["walk_interval"])
                        status = inventory_records.update_one(
                            {"address": ir.address, "port": ir.port},
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

                        task_config = gen_walk_task(ir, profile)
                        periodic_obj.manage_task(**task_config)

                except Exception as e:
                    inventory_errors = True
                    logger.exception(f"Exception raised for {target}: {e}")

    return inventory_errors


if __name__ == "__main__":
    r = load()
    if r:
        sys.exit(1)
