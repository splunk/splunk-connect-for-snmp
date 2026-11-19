import ipaddress
import logging
import os
import sys
from contextlib import suppress

import pymongo
import yaml

from splunk_connect_for_snmp import customtaskmanager
from splunk_connect_for_snmp.common.common import human_bool
from splunk_connect_for_snmp.common.customised_json_formatter import (
    CustomisedJSONFormatter,
)
from splunk_connect_for_snmp.common.discovery_record import DiscoveryRecord
from splunk_connect_for_snmp.common.task_generator import DiscoveryTaskGenerator
from splunk_connect_for_snmp.poller import app

with suppress(ImportError, OSError):
    from dotenv import load_dotenv

    load_dotenv()

DISCOVERY_CONFIG_PATH = os.getenv(
    "DISCOVERY_CONFIG_PATH", "/app/discovery/discovery-config.yaml"
)
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "sc4snmp")
CONFIG_FROM_MONGO = human_bool(os.getenv("CONFIG_FROM_MONGO", "false").lower())
CHAIN_OF_TASKS_EXPIRY_TIME = int(os.getenv("CHAIN_OF_TASKS_EXPIRY_TIME", "60"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

formatter = CustomisedJSONFormatter()

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)

# writing to stdout
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(LOG_LEVEL)
handler.setFormatter(formatter)
logger.addHandler(handler)


def autodiscovery_task_definition(discovery_record, app):
    discovery_definition = DiscoveryTaskGenerator(
        discovery_record=discovery_record, app=app
    )
    task_config = discovery_definition.generate_task_definition()
    return task_config


def check_ipv6(subnet):
    network = ipaddress.ip_network(subnet, strict=False)
    return isinstance(network, ipaddress.IPv6Network)


def configure_discovery_ui_database(mongo_client, file_autodiscovery):
    """
    Returns the autodiscovery entries that should be scheduled. When CONFIG_FROM_MONGO is enabled the entries are
    read from the discovery_ui collection (managed by the UI), which is seeded from the configuration file the first
    time the Mongo mode is used. When it's disabled again, the collection is dropped and the file is used.

    The flag is kept in its own collection (used_ui_discovery) and not in used_ui, because the inventory and the
    discovery loaders can run at the same time and both upsert their flag.
    """
    database = mongo_client[MONGO_DB]
    used_ui_collection = database.used_ui_discovery
    used_ui_doc = used_ui_collection.find_one() or {}
    used_ui = used_ui_doc.get("used_ui_discovery", False)
    discovery_collection = database.discovery_ui

    if CONFIG_FROM_MONGO and not used_ui:
        existing_names = {
            document["name"] for document in discovery_collection.find({}, {"name": 1})
        }
        documents = [
            dict(value, name=name)
            for name, value in file_autodiscovery.items()
            if name not in existing_names
        ]
        if documents:
            discovery_collection.insert_many(documents)
        used_ui_collection.update_one(
            {}, {"$set": {"used_ui_discovery": True}}, upsert=True
        )
    elif not CONFIG_FROM_MONGO and used_ui:
        discovery_collection.drop()
        used_ui_collection.update_one(
            {}, {"$set": {"used_ui_discovery": False}}, upsert=True
        )

    if CONFIG_FROM_MONGO:
        return {
            document["name"]: {
                key: value
                for key, value in document.items()
                if key not in ("_id", "name")
            }
            for document in discovery_collection.find({}, {"_id": 0})
        }
    return file_autodiscovery


def load():
    try:
        with open(DISCOVERY_CONFIG_PATH, encoding="utf-8") as file:
            config_runtime = yaml.safe_load(file)
        ipv6_enabled = config_runtime.get("ipv6Enabled", False)
        autodiscovery = config_runtime.get("autodiscovery", {}) or {}
        if MONGO_URI:
            mongo_client = pymongo.MongoClient(MONGO_URI)
            try:
                autodiscovery = configure_discovery_ui_database(
                    mongo_client, autodiscovery
                )
            finally:
                mongo_client.close()
        elif CONFIG_FROM_MONGO:
            raise ValueError("MONGO_URI is required when CONFIG_FROM_MONGO is enabled")
        periodic_obj = customtaskmanager.CustomPeriodicTaskManager()
        expiry_time_changed = periodic_obj.did_expiry_time_change(
            CHAIN_OF_TASKS_EXPIRY_TIME, [customtaskmanager.DISCOVERY_TASK]
        )
        if expiry_time_changed:
            logger.info(
                f"Task expiry time was modified, generating new tasks for discovery"
            )

        active_schedules = []
        for key, value in autodiscovery.items():
            value["discovery_name"] = key
            discovery_record = DiscoveryRecord(**value)
            is_ipv6 = check_ipv6(value["network_address"])
            if not is_ipv6 or (is_ipv6 and ipv6_enabled):
                logger.info(f"Adding the task for {key}")
                task_config = autodiscovery_task_definition(
                    discovery_record=discovery_record, app=app
                )
                periodic_obj.manage_task(**task_config)
                active_schedules.append(task_config["name"])
            else:
                logger.info(
                    f"Skipping task for the discovery: {key} because IPv6 is disabled."
                )
        periodic_obj.delete_unused_discovery_tasks(active_schedules)
        return 0
    except Exception as e:
        logger.error(f"Error occurred while creating the task: {e}")
        raise


if __name__ == "__main__":
    r = load()
    if r:
        sys.exit(0)
