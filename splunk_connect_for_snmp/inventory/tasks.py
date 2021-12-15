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
import time

import typing

from splunk_connect_for_snmp.common.profiles import load_profiles
from splunk_connect_for_snmp.snmp.manager import getInventory

try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass
import os
import re

import pymongo
import urllib3
from celery import Task, shared_task
from celery.canvas import chain, signature
from celery.utils.log import get_task_logger

from splunk_connect_for_snmp import customtaskmanager
from splunk_connect_for_snmp.common.hummanbool import human_bool


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = get_task_logger(__name__)

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "sc4snmp")
CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.yaml")
PROFILES_RELOAD_DELAY = int(os.getenv("PROFILES_RELOAD_DELAY", "300"))


class InventoryTask(Task):
    def __init__(self):
        self.profiles = load_profiles()
        self.last_modified = time.time()


@shared_task(bind=True, base=InventoryTask)
def inventory_setup_poller(self, work):
    address = work["address"]
    if time.time() - self.last_modified > PROFILES_RELOAD_DELAY:
        self.profiles = load_profiles()
        self.last_modified = time.time()
        logger.debug(f"Profiles reloaded")

    periodic_obj = customtaskmanager.CustomPeriodicTaskManager()

    mongo_client = pymongo.MongoClient(MONGO_URI)
    mongo_db = mongo_client[MONGO_DB]

    mongo_inventory = mongo_db.inventory
    targets_collection = mongo_db.targets

    ir = getInventory(mongo_inventory, address)

    target = targets_collection.find_one(
        {"address": address},
        {"target": True, "state": True, "config": True},
    )
    assigned_profiles: dict[int, list[str]] = {}

    if ir.SmartProfiles:
        for profile_name, profile in self.profiles.items():
            logger.debug(f"Checking match for {profile_name} {profile}")

            # Skip this profile its disabled
            if human_bool(profile.get("disabled", False), default=False):
                logger.debug(f"Skipping disabled profile {profile_name}")
                continue

            if "frequency" not in profile:
                logger.warn(f"Profile {profile_name} has no frequency")
                continue

            if "condition" not in profile:
                continue

            if "type" not in profile["condition"]:
                logger.warn(f"Profile {profile_name} condition has no type")
                continue

            if profile["condition"]["type"] not in ("base", "field"):
                logger.info("Profile is not smart")
                continue

            if (
                profile["condition"]["type"] == "field"
                and "field" not in profile["condition"]
            ):
                logger.warn(f"Profile {profile_name} condition has no field")
                continue
            if (
                profile["condition"]["type"] == "field"
                and "patterns" not in profile["condition"]
            ):
                logger.warn(f"Profile {profile_name} condition has no patterns")
                continue

            # skip this profile it is static
            if profile["condition"]["type"] == "base":
                logger.debug(f"Adding base profile {profile_name}")
                logger.debug(f"profile is a base {profile_name}")
                if profile["frequency"] not in assigned_profiles:
                    assigned_profiles[profile["frequency"]] = []
                assigned_profiles[profile["frequency"]].append(profile_name)

            elif profile["condition"]["type"] == "field":
                logger.debug(f"profile is a field condition {profile_name}")
                if "state" in target:
                    if (
                        profile["condition"]["field"].replace(".", "|")
                        in target["state"]
                    ):
                        cs = target["state"][
                            profile["condition"]["field"].replace(".", "|")
                        ]

                        if not isinstance(profile["condition"]["patterns"], typing.List):
                            logger.warn(f"Patterns for profile {profile_name} must be a list")
                        else:
                            for pattern in profile["condition"]["patterns"]:

                                result = re.search(pattern, cs["value"])
                                if result:
                                    logger.debug(f"Adding smart profile {profile_name}")
                                    if profile["frequency"] not in assigned_profiles:
                                        assigned_profiles[profile["frequency"]] = []
                                    assigned_profiles[profile["frequency"]].append(
                                        profile_name
                                    )
                                    continue
    logger.debug(f"{ir.profiles}")
    for profile_name in ir.profiles:
        if profile_name in self.profiles:
            profile = self.profiles[profile_name]
            if profile["frequency"] not in assigned_profiles:
                assigned_profiles[profile["frequency"]] = []
            assigned_profiles[profile["frequency"]].append(profile_name)

    logger.debug(f"Profiles Assigned {assigned_profiles}")

    activeschedules: list[str] = []
    for period in assigned_profiles:
        run_immediately: bool = False
        if period > 300:
            run_immediately = True
        name = f"sc4snmp;{address};{period};poll"
        period_profiles = set(assigned_profiles[period])
        activeschedules.append(name)

        task_config = {
            "name": name,
            "task": "splunk_connect_for_snmp.snmp.tasks.poll",
            "target": f"{address}",
            "args": [],
            "kwargs": {
                "address": address,
                "profiles": period_profiles,
                "frequency": period,
            },
            "options": {
                "link": chain(
                    signature("splunk_connect_for_snmp.enrich.tasks.enrich"),
                    chain(
                        signature("splunk_connect_for_snmp.splunk.tasks.prepare"),
                        signature("splunk_connect_for_snmp.splunk.tasks.send"),
                    ),
                ),
            },
            "interval": {"every": period, "period": "seconds"},
            "enabled": True,
            "run_immediately": run_immediately,
        }
        periodic_obj.manage_task(**task_config)
    periodic_obj.delete_unused_poll_tasks(f"{address}", activeschedules)
    periodic_obj.delete_disabled_poll_tasks()
