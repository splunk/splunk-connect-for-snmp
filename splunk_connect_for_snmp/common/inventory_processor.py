import copy
import logging
import os
from csv import DictReader
from typing import List

from splunk_connect_for_snmp.common.collection_manager import GroupsManager
from splunk_connect_for_snmp.common.inventory_record import InventoryRecord
from splunk_connect_for_snmp.common.task_generator import WalkTaskGenerator
from splunk_connect_for_snmp.poller import app

try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass


CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.yaml")
INVENTORY_PATH = os.getenv("INVENTORY_PATH", "/app/inventory/inventory.csv")


def transform_key_to_address(target):
    if ":" in target:
        address, port = target.split(":")
    else:
        return target, 161
    return address, int(port)


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


def return_hosts_from_deleted_groups(previous_groups, new_groups):
    inventory_lines_to_delete = []
    for group_name in previous_groups.keys():
        if group_name not in new_groups:
            inventory_lines_to_delete += previous_groups[group_name]
        else:
            deleted_hosts = set(previous_groups.get(group_name)) - set(
                new_groups.get(group_name)
            )
            inventory_lines_to_delete += deleted_hosts
    return inventory_lines_to_delete


class InventoryProcessor:
    def __init__(self, group_manager: GroupsManager, logger):
        self.inventory_records: List[dict] = []
        self.group_manager = group_manager
        self.logger = logger

    def get_all_hosts(self):
        self.logger.info(f"Loading inventory from {INVENTORY_PATH}")
        with open(INVENTORY_PATH, encoding="utf-8") as csv_file:
            ir_reader = DictReader(csv_file)
            for inventory_line in ir_reader:
                self.process_line(inventory_line)
        return self.inventory_records

    def process_line(self, source_record):
        address = source_record["address"]
        # Inventory record is commented out
        if address.startswith("#"):
            self.logger.warning(f"Record: {address} is commented out. Skipping...")
        # Address is an IP address
        elif address[0].isdigit():
            self.inventory_records.append(address)
        # Address is a group
        else:
            self.get_group_hosts(source_record, address)

    def get_group_hosts(self, group_object, group_name):
        groups = self.group_manager.return_element(group_name, {"$exists": 1})
        if groups:
            print(group_object)
            addresses = list(groups[0].values())
            for host_address in addresses[0]:
                address, port = transform_key_to_address(host_address)
                host_group_object = copy.copy(group_object)
                host_group_object["address"] = address
                host_group_object["port"] = port
                self.inventory_records.append(host_group_object)
        else:
            self.logger.warning(
                f"Group {group_name} doesn't exist in the configuration. Skipping..."
            )


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
        self.targets_collection.remove({"address": target})
        self.attributes_collection.remove({"address": target})
        self.logger.info(f"Deleting record: {target}")

    def update(self, inventory_record, new_source_record, runtime_profiles):
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
            return
        task_config = gen_walk_task(inventory_record, walk_profile)
        self.periodic_object_collection.manage_task(**task_config)

    def return_walk_profile(self, runtime_profiles, inventory_profiles):
        print(runtime_profiles)
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
