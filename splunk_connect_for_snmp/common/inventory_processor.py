import copy
import os
from contextlib import suppress
from csv import DictReader
from typing import List

import pymongo

from splunk_connect_for_snmp.common.collection_manager import GroupsManager
from splunk_connect_for_snmp.common.hummanbool import human_bool
from splunk_connect_for_snmp.common.inventory_record import InventoryRecord
from splunk_connect_for_snmp.common.task_generator import WalkTaskGenerator
from splunk_connect_for_snmp.poller import app

with suppress(ImportError, OSError):
    from dotenv import load_dotenv

    load_dotenv()

CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.yaml")
INVENTORY_PATH = os.getenv("INVENTORY_PATH", "/app/inventory/inventory.csv")
CONFIG_FROM_MONGO = human_bool(os.getenv("CONFIG_FROM_MONGO", "false").lower())
ALLOWED_KEYS_VALUES = [
    "address",
    "port",
    "community",
    "secret",
    "version",
    "security_engine",
    "securityEngine",
]


def transform_key_to_address(target):
    if ":" in target:
        address, port = target.split(":")
    else:
        return target, 161
    return address, int(port)


def transform_address_to_key(address, port):
    if not port or int(port) == 161:
        return address
    else:
        return f"{address}:{port}"


def gen_walk_task(ir: InventoryRecord, profile=None, group=None):
    target = transform_address_to_key(ir.address, ir.port)
    walk_definition = WalkTaskGenerator(
        target=target,
        schedule_period=ir.walk_interval,
        app=app,
        host_group=group,
        profile=profile,
    )
    task_config = walk_definition.generate_task_definition()
    return task_config


def return_hosts_from_deleted_groups(
    previous_groups, new_groups, inventory_group_port_mapping
):
    inventory_lines_to_delete = []
    for group_name in previous_groups.keys():
        previous_groups_keys = get_groups_keys(
            previous_groups[group_name], group_name, inventory_group_port_mapping
        )
        if group_name not in new_groups:
            inventory_lines_to_delete += previous_groups_keys
        else:
            new_groups_keys = get_groups_keys(
                new_groups[group_name], group_name, inventory_group_port_mapping
            )
            deleted_hosts = set(previous_groups_keys) - set(new_groups_keys)
            inventory_lines_to_delete += deleted_hosts
    return inventory_lines_to_delete


def get_groups_keys(list_of_groups, group_name, inventory_group_port_mapping):
    group_port = inventory_group_port_mapping.get(group_name, 161)
    groups_keys = [
        f"{transform_address_to_key(element.get('address'), element.get('port', group_port))}"
        for element in list_of_groups
    ]
    return groups_keys


class InventoryProcessor:
    def __init__(self, group_manager: GroupsManager, logger, inventory_ui_collection):
        self.inventory_records: List[dict] = []
        self.group_manager = group_manager
        self.logger = logger
        self.hosts_from_groups: dict = {}
        self.inventory_group_port_mapping: dict = {}
        self.single_hosts: List[dict] = []
        self.inventory_ui_collection = inventory_ui_collection

    def get_all_hosts(self):
        if CONFIG_FROM_MONGO:
            self.logger.info("Loading inventory from inventory_ui collection")
            ir_reader = list(self.inventory_ui_collection.find({}, {"_id": 0}))
        else:
            with open(INVENTORY_PATH, encoding="utf-8") as csv_file:
                self.logger.info(f"Loading inventory from {INVENTORY_PATH}")
                ir_reader = list(DictReader(csv_file))
        for inventory_line in ir_reader:
            self.process_line(inventory_line)
        for source_record in self.single_hosts:
            address = source_record["address"]
            port = source_record.get("port")
            host = transform_address_to_key(address, port)
            was_present = self.hosts_from_groups.get(host, None)
            if was_present is None:
                self.inventory_records.append(source_record)
            else:
                self.logger.warning(
                    f"Record: {host} has been already configured in group. Skipping..."
                )
        return self.inventory_records, self.inventory_group_port_mapping

    def process_line(self, source_record):
        address = source_record["address"]
        # Inventory record is commented out
        if address.startswith("#"):
            self.logger.warning(f"Record: {address} is commented out. Skipping...")
        # Address is an IP address
        elif address[0].isdigit():
            self.single_hosts.append(source_record)
        # Address is a group
        else:
            self.get_group_hosts(source_record, address)

    def get_group_hosts(self, source_object, group_name):
        groups = self.group_manager.return_element(group_name, {"$exists": 1})
        group_list = list(groups)
        if group_list:
            groups_object_list = list(group_list[0].values())
            self.inventory_group_port_mapping[group_name] = (
                source_object["port"] if source_object["port"] else 161
            )
            for group_object in groups_object_list[0]:
                host_group_object = copy.copy(source_object)
                for key in group_object.keys():
                    if key in ALLOWED_KEYS_VALUES:
                        host_group_object[key] = group_object[key]
                    else:
                        self.logger.warning(
                            f"Key {key} is not allowed to be changed from the group level"
                        )
                address = str(group_object["address"])
                port = group_object.get("port")
                host = transform_address_to_key(address, port)
                self.hosts_from_groups[host] = True
                host_group_object["group"] = group_name
                self.inventory_records.append(host_group_object)
        else:
            self.logger.warning(
                f"Group {group_name} doesn't exist in the configuration. Treating {group_name} as a hostname"
            )
            self.single_hosts.append(source_object)


class InventoryRecordManager:
    def __init__(self, mongo_client, periodic_objects_collection, logger):
        self.targets_collection = mongo_client.sc4snmp.targets
        self.inventory_collection = mongo_client.sc4snmp.inventory
        self.attributes_collection = mongo_client.sc4snmp.attributes
        self.periodic_object_collection = periodic_objects_collection
        self.logger = logger

    def delete(self, target):
        address, port = transform_key_to_address(target)
        self.periodic_object_collection.delete_all_tasks_of_host(target)
        self.inventory_collection.delete_one({"address": address, "port": port})
        self.targets_collection.delete_many({"address": target})
        self.attributes_collection.delete_many({"address": target})
        self.logger.info(f"Deleting record: {target}")

    def update(
        self, inventory_record, new_source_record, runtime_profiles, expiry_time_changed
    ):
        profiles = new_source_record["profiles"].split(";")
        walk_profile = self.return_walk_profile(runtime_profiles, profiles)
        if walk_profile:
            inventory_record.walk_interval = int(new_source_record["walk_interval"])
        status = self.inventory_collection.update_one(
            {"address": inventory_record.address, "port": inventory_record.port},
            {"$set": inventory_record.asdict()},
            upsert=True,
        )
        if status.matched_count == 0:
            self.logger.info(f"New Record {inventory_record} {status.upserted_id}")
        elif status.modified_count == 1 and status.upserted_id is None:
            self.logger.info(f"Modified Record {inventory_record}")
        else:
            self.logger.info(f"Unchanged Record {inventory_record}")
            if expiry_time_changed:
                self.logger.info(
                    f"Task expiry time was modified, generating new tasks for record {inventory_record}"
                )
            else:
                return
        task_config = gen_walk_task(
            inventory_record,
            walk_profile,
            new_source_record.get("group"),
        )
        self.periodic_object_collection.manage_task(**task_config)

    def return_walk_profile(self, runtime_profiles, inventory_profiles):
        walk_profile = None
        if inventory_profiles:
            walk_profiles = [
                p
                for p in inventory_profiles
                if runtime_profiles.get(p, {}).get("condition", {}).get("type")
                == "walk"
            ]
            if walk_profiles:
                # if there's more than one walk profile, we're choosing the last one on the list
                walk_profile = walk_profiles[-1]
        return walk_profile
