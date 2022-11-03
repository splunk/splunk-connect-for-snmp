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

from pymongo import ASCENDING
from csv import DictReader
import yaml

from splunk_connect_for_snmp.common.customised_json_formatter import (
    CustomisedJSONFormatter,
)

from ..poller import app
from .task_generator import WalkTaskGenerator

formatter = CustomisedJSONFormatter()

logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")

# writing to stdout
handler = logging.StreamHandler(sys.stdout)
handler.setLevel("DEBUG")
handler.setFormatter(formatter)
logger.addHandler(handler)


CURRENT_SCHEMA_VERSION = 6
MONGO_URI = os.getenv("MONGO_URI")
CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.yaml")
INVENTORY_PATH = os.getenv("INVENTORY_PATH", "/app/inventory/inventory.csv")

INVENTORY_KEYS_TRANSFORM = {
    "securityEngine": "security_engine",
    "SmartProfiles": "smart_profiles"
}
BOOLEAN_INVENTORY_FIELDS = ["delete", "smart_profiles"]


def fetch_schema_version(mongo_client):
    schema_collection = mongo_client.sc4snmp.schema_version
    schema_version = schema_collection.find_one()

    if schema_version:
        return schema_version["version"]
    else:
        return 0


def save_schema_version(mongo_client, version):
    schema_collection = mongo_client.sc4snmp.schema_version

    schema_collection.update_one({}, {"$set": {"version": version}}, upsert=True)


def migrate_database(mongo_client, periodic_obj):
    previous_schema_version = fetch_schema_version(mongo_client)
    if previous_schema_version < CURRENT_SCHEMA_VERSION:
        logger.info(
            f"Migrating from version {previous_schema_version} to version {CURRENT_SCHEMA_VERSION}"
        )

        for x in range(previous_schema_version, CURRENT_SCHEMA_VERSION):
            fun_name = "migrate_to_version_" + str(x + 1)
            getattr(sys.modules[__name__], fun_name)(mongo_client, periodic_obj)

        save_schema_version(mongo_client, CURRENT_SCHEMA_VERSION)


def migrate_to_version_1(mongo_client, task_manager):
    logger.info("Migrating database schema to version 1")
    targets_collection = mongo_client.sc4snmp.targets

    task_manager.delete_all_poll_tasks()
    targets_collection.update({}, {"$unset": {"attributes": 1}}, False, True)
    task_manager.rerun_all_walks()


def migrate_to_version_2(mongo_client, task_manager):
    logger.info("Migrating database schema to version 2")
    attributes_collection = mongo_client.sc4snmp.attributes

    task_manager.delete_all_poll_tasks()
    attributes_collection.drop()
    task_manager.rerun_all_walks()


def migrate_to_version_3(mongo_client, task_manager):
    logger.info("Migrating database schema to version 3")
    attributes_collection = mongo_client.sc4snmp.attributes

    attributes_collection.create_index(
        [("address", ASCENDING), ("group_key_hash", ASCENDING)]
    )


def migrate_to_version_4(mongo_client, task_manager):
    logger.info("Migrating database schema to version 4")
    schedules_collection = mongo_client.sc4snmp.schedules
    transform_mongodb_periodic_to_redbeat(schedules_collection, task_manager)
    schedules_collection.drop()


def migrate_to_version_5(mongo_client, task_manager):
    logger.info("Migrating database schema to version 5")
    inventory_collection = mongo_client.sc4snmp.inventory
    inventory_collection.update_many({}, {"$set": {"group": None}})


def migrate_to_version_6(mongo_client, task_manager):
    inventory_collection = mongo_client.sc4snmp.inventory_ui
    groups_collection = mongo_client.sc4snmp.groups_ui
    profiles_collection = mongo_client.sc4snmp.profiles_ui

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

            port = int(inventory_line['port']) if len(inventory_line['port']) > 0 else 161
            walk_interval = int(inventory_line["walk_interval"]) if int(inventory_line["walk_interval"]) >= 1800 else 1800
            inventory_line['port'] = port
            inventory_line['walk_interval'] = walk_interval
            inventory_collection.insert(inventory_line)

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
                    f"loading {len(profiles.keys())} profiles from runtime profile group"
                )
                for key, profile in profiles.items():
                    all_profiles[key] = profile
    except FileNotFoundError:
        logger.info(f"File: {CONFIG_PATH} not found")

    groups_list = [{key: value} for key, value in groups.items()]
    groups_collection.insert_many(groups_list)
    profiles_list = [{key: value} for key, value in all_profiles.items()]
    profiles_collection.insert_many(profiles_list)


def transform_mongodb_periodic_to_redbeat(schedule_collection, task_manager):
    schedules = schedule_collection.find(
        {"task": "splunk_connect_for_snmp.snmp.tasks.walk"}
    )
    for schedule_obj in schedules:
        walk_interval = schedule_obj.get("interval").get("every")
        task_generator = WalkTaskGenerator(
            target=schedule_obj.get("target"),
            schedule_period=walk_interval,
            app=app,
            profile=schedule_obj.get("kwargs").get("profile"),
            host_group=None,
        )
        walk_data = task_generator.generate_task_definition()
        task_manager.manage_task(**walk_data)
