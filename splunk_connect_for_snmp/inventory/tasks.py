from splunk_connect_for_snmp.common.inventory_record import InventoryRecord

try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass

import csv
import os
import re

import pymongo
import urllib3
import yaml
from bson.objectid import ObjectId
from celery import shared_task, signature
from celery.utils.log import get_task_logger

from splunk_connect_for_snmp import customtaskmanager

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from typing import List, Union

logger = get_task_logger(__name__)

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "sc4")


def isTrueish(flag: Union[str, bool]) -> bool:

    if isinstance(flag, bool):
        return flag

    if flag.lower() in [
        "true",
        "1",
        "t",
        "y",
        "yes",
    ]:
        return True
    else:
        return False


def isFalseish(flag: Union[str, bool]) -> bool:
    if isinstance(flag, bool):
        return flag
    if flag.lower() in [
        "false",
        "0",
        "f",
        "n",
        "no",
    ]:
        return True
    else:
        return False


@shared_task()
# This task gets the inventory and creates a task to schedules each walk task
def inventory_seed(path=None):
    mongo_client = pymongo.MongoClient(MONGO_URI)
    targets_collection = mongo_client.sc4.targets

    periodic_obj = customtaskmanager.CustomPeriodicTaskManage()

    dict_from_csv = {}
    with open(path) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        line_count = 0
        for target in csv_reader:
            if line_count == 0:
                print(f'Column names are {", ".join(target)}')
                line_count += 1
                continue
            logger.debug(f"Inventory record {target}")
            target_update = []
            ir = InventoryRecord(*target)
            # The default port is 161
            if len(ir.ip.split(":")) == 1:
                ir.ip = f"{ir.ip}:161"

            try:
                wi = float(ir.walk_interval)
                if wi < 0 or wi > 42000:
                    ir.walk_interval = 42000
            except:
                ir.walk_interval = 42000

            if "delete" in target and isTrueish(ir.delete):
                periodic_obj.delete_task(ir.ip)
            else:
                if ir.version not in ("1", "2", "2c", "3"):
                    logger.error("Invalid version in inventory record {row}")
                    continue
                if ir.version == "3" and ir.community == "public":
                    logger.error(
                        "Invalid community in inventory record {row} when version=3 community can not be public"
                    )
                    continue

                if len(ir.community.strip()) == 0:
                    logger.error(
                        "Invalid community in inventory record {row} must not be blank"
                    )
                    continue

                updates = []
                # TODO: if SmartProfiles or profiles is changed we need to set the immediate flag on walk
                updates.append(
                    {
                        "$set": {
                            "config": {
                                "community": {
                                    "version": ir.version,
                                    "name": ir.community,
                                }
                            }
                        }
                    }
                )
                profiles: List[str] = []
                if len(ir.profiles.strip()) > 0:
                    profiles = ir.profiles.split(";")

                SmartProfiles: bool = True
                if isFalseish(ir.SmartProfiles):
                    SmartProfiles = False

                updates.append(
                    {
                        "$set": {
                            "config": {
                                "profiles": {
                                    "SmartProfiles": SmartProfiles,
                                    "StaticProfiles": profiles,
                                }
                            }
                        }
                    }
                )
                ur = targets_collection.update_one(
                    {"target": ir.ip}, updates, upsert=True
                )
                fr = targets_collection.find_one(
                    {"target": ir.ip}, {"_id": True}
                )
                task_config = {
                    "name": f"sc4snmp;{ir.ip};walk",
                    "task": "splunk_connect_for_snmp.snmp.tasks.walk",
                    "target": f"{ir.ip}",
                    "args": [],
                    "kwargs": {"id": str(fr['_id'])},
                    "interval": {"every": ir.walk_interval, "period": "seconds"},
                    "enabled": True,
                    "run_immediately": True,
                }
                if ur.modified_count:
                    logger.debug("Device Config Changed need to walk")
                    logger.info(f"Upserted id: {fr['_id']}")
                    task_config["kwargs"]["id"] = str(fr['_id'])
                    task_config["run_immediately"] = True
                else:
                    task_config["kwargs"]["id"] = str(fr["_id"])
                logger.debug(task_config)
                periodic_obj.manage_task(run_immediately_if_new=True, **task_config)
    return True


@shared_task()
def inventory_setup_poller(**kwargs):

    with open("config.yaml", "r") as file:
        config_base = yaml.safe_load(file)

    periodic_obj = customtaskmanager.CustomPeriodicTaskManage()
    profiles: list[str] = []

    mongo_client = pymongo.MongoClient(MONGO_URI)
    targets_collection = mongo_client.sc4.targets

    target = targets_collection.find_one(
        {"_id": ObjectId(kwargs["id"])},
        {"target": True, "state": True, "config": {"profiles": True}},
    )
    smart_profiles: dict[int, list[str]] = {}
    logger.debug(f"target is target {target}")
    logger.debug(f" Config base is {config_base}")
    if target["config"]["profiles"]["SmartProfiles"]:
        for profile_name, profile in config_base["poller"]["profiles"].items():
            logger.debug(f"Checking match for {profile_name} {profile}")

            # Skip this profile its disabled
            if isTrueish(profile.get("disabled", False)):
                logger.debug(f"Skipping disabled profile {profile_name}")
                continue

            if not "frequency" in profile:
                logger.error(f"Profile {profile_name} has no frequency")
                continue

            if not "condition" in profile:
                logger.error(f"Profile {profile_name} has no condition")
                continue

            if not "type" in profile["condition"]:
                logger.error(f"Profile {profile_name} condition has no type")
                continue

            if profile["condition"]["type"] not in ("base", "field"):
                logger.info("Profile is not smart")
                continue

            if (
                profile["condition"]["type"] == "field"
                and not "field" in profile["condition"]
            ):
                logger.error(f"Profile {profile_name} condition has no field")
                continue
            if (
                profile["condition"]["type"] == "field"
                and not "patterns" in profile["condition"]
            ):
                logger.error(f"Profile {profile_name} condition has no patterns")
                continue

            # skip this profile it is static
            if profile["condition"]["type"] == "base":
                logger.debug(f"Adding base profile {profile_name}")
                logger.debug(f"profile is a base {profile_name}")
                if not profile["frequency"] in smart_profiles:
                    smart_profiles[profile["frequency"]] = []
                smart_profiles[profile["frequency"]].append(profile_name)

            elif profile["condition"]["type"] == "field":
                logger.debug(f"profile is a field condition {profile_name}")

                if profile["condition"]["field"].replace(".", "|") in target["state"]:
                    cs = target["state"][
                        profile["condition"]["field"].replace(".", "|")
                    ]

                    for pattern in profile["condition"]["patterns"]:

                        result = re.match(pattern, cs["value"])
                        if result:
                            logger.debug(f"Adding smart profile {profile_name}")
                            if not profile["frequency"] in smart_profiles:
                                smart_profiles[profile["frequency"]] = []
                            smart_profiles[profile["frequency"]].append(profile_name)
                            continue

        logger.debug(f"Smart Profiles Assigned {smart_profiles}")
        activeschedules: list[str] = []
        for period in smart_profiles:
            run_immediately: bool = False
            if period > 300:
                run_immediately = True
            name = f"sc4snmp;{target['target']};{period};poll"
            activeschedules.append(name)
            task_config = {
                "name": name,
                "task": "splunk_connect_for_snmp.snmp.tasks.poll",
                "target": f"{target['target']}",
                "args": [],
                "kwargs": {"id": kwargs["id"], "profiles": set(smart_profiles[period])},
                # TODO: Make the inteval from profile
                "interval": {"every": period, "period": "seconds"},
                "enabled": True,
                "run_immediately": run_immediately,
            }
            periodic_obj.manage_task(**task_config)
        periodic_obj.delete_unused_poll_tasks(f"{target['target']}", activeschedules)
