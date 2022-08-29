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

import pymongo

from splunk_connect_for_snmp import customtaskmanager
from splunk_connect_for_snmp.common.collection_manager import (
    GroupsManager,
    ProfilesManager,
)
from splunk_connect_for_snmp.common.customised_json_formatter import (
    CustomisedJSONFormatter,
)
from splunk_connect_for_snmp.common.inventory_processor import (
    InventoryProcessor,
    InventoryRecordManager,
    return_hosts_from_deleted_groups,
    transform_address_to_key,
)
from splunk_connect_for_snmp.common.inventory_record import InventoryRecord
from splunk_connect_for_snmp.common.schema_migration import migrate_database

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

    previous_groups = groups_manager.return_collection()
    logger.info(f"Previous groups: {previous_groups}")

    # Read the config file and update MongoDB collections
    profiles_manager.update_all()
    groups_manager.update_all()

    # Read objects necessary for inventory processing
    config_profiles = profiles_manager.return_collection()
    new_groups = groups_manager.return_collection()

    inventory_processor = InventoryProcessor(groups_manager, logger)
    inventory_record_manager = InventoryRecordManager(
        mongo_client, periodic_obj, logger
    )
    logger.info(f"Loading inventory from {INVENTORY_PATH}")
    inventory_lines = inventory_processor.get_all_hosts()
    print(inventory_lines)

    # Function to delete inventory records that are
    hosts_from_groups_to_delete = return_hosts_from_deleted_groups(
        previous_groups, new_groups
    )
    for host in hosts_from_groups_to_delete:
        inventory_record_manager.delete(host)

    for new_source_record in inventory_lines:
        try:
            ir = InventoryRecord(**new_source_record)
            target = transform_address_to_key(ir.address, ir.port)
            if ir.delete:
                inventory_record_manager.delete(target)
            else:
                inventory_record_manager.update(
                    ir, new_source_record, config_profiles, new_groups
                )

        except Exception as e:
            inventory_errors = True
            logger.exception(f"Exception raised for {target}: {e}")

    return inventory_errors


if __name__ == "__main__":
    r = load()
    if r:
        sys.exit(1)
