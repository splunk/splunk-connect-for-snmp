try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass

import csv
import os
import sys
import traceback
from io import StringIO

import pymongo
import urllib3
import yaml
from bson.objectid import ObjectId
from celery import shared_task, signature
from celery.utils.log import get_task_logger
from requests_cache import MongoCache

from splunk_connect_for_snmp import customtaskmanager
from splunk_connect_for_snmp.common.requests import CachedLimiterSession
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from typing import Union, List

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
def inventory_seed(url=None, tlsverify=True):
    logger.info(f"url %{url}")

    mongo_client = pymongo.MongoClient(MONGO_URI)
    targets_collection = mongo_client.sc4.targets

    periodic_obj = customtaskmanager.CustomPeriodicTaskManage()
    session = CachedLimiterSession(
        per_second=120,
        cache_name="cache_http",
        backend=MongoCache(url=MONGO_URI, db=MONGO_DB),
        expire_after=300,
        logger=logger,
        match_headers=False,
        stale_if_error=True,
    )
    response = session.request(
        "GET",
        url,
        timeout=60,
        verify=tlsverify,
    )
    logger.debug(f"result={response.text}")

    dict_from_csv = {}
    with StringIO(response.text) as infile:
        reader = csv.reader(infile)
        headers = next(reader)[0:]
        for row in reader:
            target = {key: value for key, value in zip(headers, row[0:])}
            logger.debug(f"Inventory record {target}")
            target_update = []

            # The default port is 161
            if len(target["address"].split(":")) == 1:
                target["address"] = f"{target['address']}:161"

            try:
                wi = float(target["walk_interval"])
                if wi < 0 or wi > 42000:
                    target["walk_interval"] = 42000
            except:
                target["walk_interval"] = 42000

            if "delete" in target and isTrueish(target["delete"]):
                periodic_obj.delete_task(target["address"])
            else:
                if not target["version"] in ("1", "2", "2c", "3"):
                    logger.error("Invalid version in inventory record {row}")
                    continue
                if target["version"] == "3" and target["community"] == "public":
                    logger.error(
                        "Invalid community in inventory record {row} when version=3 community can not be public"
                    )
                    continue

                if len(target["community"].strip()) == 0:
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
                                    "version": target["version"],
                                    "name": target["community"],
                                }
                            }
                        }
                    }
                )
                profiles: list[str] = []
                if len(target["profiles"].strip()) > 0:
                    profiles = target["profiles"].split(";")

                SmartProfiles: bool = True
                if isFalseish(target["SmartProfiles"]):
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
                    {"target": target["address"]}, updates, upsert=True
                )

                task_config = {
                    "name": f"sc4snmp;{target['address']};walk",
                    "task": "splunk_connect_for_snmp.snmp.tasks.walk",
                    "target": f"{target['address']}",
                    "args": [],
                    "kwargs": {},
                    "interval": {"every": target["walk_interval"], "period": "seconds"},
                    "enabled": True,
                }
                if ur.modified_count > 0:
                    logger.debug("Device Config Changed need to walk")
                    task_config["kwargs"]["id"] = str(ur["_id"])
                    task_config["run_immediately"] = True
                else:
                    fr = targets_collection.find_one(
                        {"target": target["address"]}, {"_id": True}
                    )
                    task_config["kwargs"]["id"] = str(fr["_id"])
                logger.debug(task_config)
                periodic_obj.manage_task(run_immediately_if_new=True, **task_config)
                # if target["profiles"].lstrip() != "":
                #     dp = target["profiles"].lstrip().split(";")
                #     for p in dp:
                #         # TODO: Check profile inventory and log error for undefined profiles
                #         task_config = {
                #             "name": f"sc4snmp;{ip};{p};poll;static",
                #             "task": "splunk_connect_for_snmp.snmp.tasks.poll",
                #             "target": f"sc4snmp;{ip}",
                #             "args": [],
                #             "kwargs": target,
                #             "interval": {"every": 20, "period": "seconds"},
                #             "enabled": False,
                #             "run_immediately": False,
                #         }
                #         periodic_obj.manage_task(**task_config)

                # TODO: Loop through static profiles and remove if needed
    return True


@shared_task()
# This task gets the inventory and creates a task to schedules each walk task
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
                logger.debug(f"Adding base profile f{profile_name}")
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
            periodic_obj.delete_unused_poll_tasks(
                f"{target['target']}", activeschedules
            )
            periodic_obj.manage_task(**task_config)
