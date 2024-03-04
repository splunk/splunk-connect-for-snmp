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
from contextlib import suppress
from csv import DictReader

import pymongo
import yaml

from splunk_connect_for_snmp import customtaskmanager
from splunk_connect_for_snmp.common.collection_manager import (
    GroupsManager,
    ProfilesManager,
)
from splunk_connect_for_snmp.common.customised_json_formatter import (
    CustomisedJSONFormatter,
)
from splunk_connect_for_snmp.common.hummanbool import human_bool
from splunk_connect_for_snmp.common.inventory_processor import (
    InventoryProcessor,
    InventoryRecordManager,
    return_hosts_from_deleted_groups,
    transform_address_to_key,
)
from splunk_connect_for_snmp.common.inventory_record import InventoryRecord
from splunk_connect_for_snmp.common.schema_migration import migrate_database

with suppress(ImportError, OSError):
    from dotenv import load_dotenv

    load_dotenv()

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
CONFIG_FROM_MONGO = human_bool(os.getenv("CONFIG_FROM_MONGO", "false").lower())
INVENTORY_KEYS_TRANSFORM = {
    "securityEngine": "security_engine",
    "SmartProfiles": "smart_profiles",
}
BOOLEAN_INVENTORY_FIELDS = ["delete", "smart_profiles"]
CHAIN_OF_TASKS_EXPIRY_TIME = int(os.getenv("CHAIN_OF_TASKS_EXPIRY_TIME", "60"))


def configure_ui_database(mongo_client):
    """
    If the UI wasn't used in previous update, and now it is used, create UI collections in Mongo
    with config from files. Similarly, if the UI was used previous update, and now it isn't used,
    drop UI collections in Mongo.
    """
    used_ui_collection = mongo_client.sc4snmp.used_ui
    used_ui_doc = used_ui_collection.find_one()
    if used_ui_doc:
        used_ui = used_ui_doc["used_ui"]
    else:
        used_ui = False

    if CONFIG_FROM_MONGO and not used_ui:
        inventory_ui_collection = mongo_client.sc4snmp.inventory_ui
        groups_ui_collection = mongo_client.sc4snmp.groups_ui
        profiles_ui_collection = mongo_client.sc4snmp.profiles_ui
        used_ui_collection.update_one({}, {"$set": {"used_ui": True}}, upsert=True)

        with open(INVENTORY_PATH, encoding="utf-8") as csv_file:
            ir_reader = DictReader(csv_file)
            for inventory_line in ir_reader:
                for key in INVENTORY_KEYS_TRANSFORM.keys():
                    if key in inventory_line:
                        new_key = INVENTORY_KEYS_TRANSFORM[key]
                        inventory_line[new_key] = inventory_line.pop(key)

                for field in BOOLEAN_INVENTORY_FIELDS:
                    if inventory_line[field].lower() in ["", "f", "false", "0"]:
                        inventory_line[field] = False
                    else:
                        inventory_line[field] = True

                port = (
                    int(inventory_line.get("port", 161))
                    if inventory_line.get("port", 161)
                    else 161
                )
                walk_interval = (
                    int(inventory_line["walk_interval"])
                    if int(inventory_line["walk_interval"]) >= 1800
                    else 1800
                )
                inventory_line["port"] = port
                inventory_line["walk_interval"] = walk_interval
                if not inventory_line["address"].startswith("#"):
                    inventory_ui_collection.insert(inventory_line)

        groups = {}
        all_profiles = {}
        try:
            with open(CONFIG_PATH, encoding="utf-8") as file:
                config_runtime = yaml.safe_load(file)
                if "groups" in config_runtime:
                    groups = config_runtime.get("groups", {})

                if "profiles" in config_runtime:
                    profiles = config_runtime.get("profiles", {})
                    logger.info(
                        f"loading {len(profiles.keys())} profiles from runtime profiles config"
                    )
                    for key, profile in profiles.items():
                        all_profiles[key] = profile
        except FileNotFoundError:
            logger.info(f"File: {CONFIG_PATH} not found")

        groups_list = [{key: value} for key, value in groups.items()]
        if groups_list:
            groups_ui_collection.insert_many(groups_list)
        profiles_list = [{key: value} for key, value in all_profiles.items()]
        if profiles_list:
            profiles_ui_collection.insert_many(profiles_list)

    elif not CONFIG_FROM_MONGO and used_ui:
        used_ui_collection.update_one({}, {"$set": {"used_ui": False}}, upsert=True)
        inventory_ui_collection = mongo_client.sc4snmp.inventory_ui
        groups_ui_collection = mongo_client.sc4snmp.groups_ui
        profiles_ui_collection = mongo_client.sc4snmp.profiles_ui
        inventory_ui_collection.drop()
        groups_ui_collection.drop()
        profiles_ui_collection.drop()


def load():
    inventory_errors = False
    target = None
    # DB managers initialization
    mongo_client = pymongo.MongoClient(MONGO_URI)
    profiles_manager = ProfilesManager(mongo_client)
    groups_manager = GroupsManager(mongo_client)
    periodic_obj = customtaskmanager.CustomPeriodicTaskManager()

    # DB migration in case of update of SC4SNMP
    migrate_database(mongo_client, periodic_obj)

    configure_ui_database(mongo_client)

    expiry_time_changed = periodic_obj.did_expiry_time_change(
        CHAIN_OF_TASKS_EXPIRY_TIME
    )

    previous_groups = groups_manager.return_collection()

    # Read the config file and update MongoDB collections
    profiles_manager.update_all()
    groups_manager.update_all()

    # Read objects necessary for inventory processing
    config_profiles = profiles_manager.return_collection()
    new_groups = groups_manager.return_collection()

    inventory_ui_collection = mongo_client.sc4snmp.inventory_ui
    inventory_processor = InventoryProcessor(
        groups_manager, logger, inventory_ui_collection
    )
    inventory_record_manager = InventoryRecordManager(
        mongo_client, periodic_obj, logger
    )
    if CONFIG_FROM_MONGO:
        logger.info(f"Loading inventory from inventory_ui collection")
    else:
        logger.info(f"Loading inventory from {INVENTORY_PATH}")
    inventory_lines, inventory_group_port_mapping = inventory_processor.get_all_hosts()

    # Function to delete inventory records that are
    hosts_from_groups_to_delete = return_hosts_from_deleted_groups(
        previous_groups, new_groups, inventory_group_port_mapping
    )
    for host in hosts_from_groups_to_delete:
        inventory_record_manager.delete(host)

    for new_source_record in inventory_lines:
        try:
            ir = InventoryRecord(**new_source_record)
            target = transform_address_to_key(ir.address, ir.port)
            if ir.delete:
                inventory_record_manager.delete(target)
                if CONFIG_FROM_MONGO:
                    if ir.group is None:
                        mongo_client.sc4snmp.inventory_ui.delete_one(
                            {"address": ir.address, "port": ir.port}
                        )
                    else:
                        mongo_client.sc4snmp.inventory_ui.delete_one(
                            {"address": ir.group}
                        )
            else:
                inventory_record_manager.update(
                    ir, new_source_record, config_profiles, expiry_time_changed
                )

        except Exception as e:
            inventory_errors = True
            if CONFIG_FROM_MONGO and new_source_record["delete"]:
                mongo_client.sc4snmp.inventory_ui.delete_one(
                    {
                        "address": new_source_record["address"],
                        "port": new_source_record["port"],
                    }
                )
            target = transform_address_to_key(
                new_source_record["address"], new_source_record["port"]
            )
            logger.exception(f"Exception raised for {target}: {e}")

    return inventory_errors


if __name__ == "__main__":
    r = load()
    if r:
        sys.exit(1)
