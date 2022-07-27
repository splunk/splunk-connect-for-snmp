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
from splunk_connect_for_snmp.snmp.manager import get_inventory
from .loader import transform_address_to_key

from ..common.task_generator import PollTaskGenerator

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
from celery.utils.log import get_task_logger

from splunk_connect_for_snmp import customtaskmanager
from splunk_connect_for_snmp.common.hummanbool import human_bool

from ..poller import app

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  # nosemgrep

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
        logger.debug("Profiles reloaded")

    periodic_obj = customtaskmanager.CustomPeriodicTaskManager()

    mongo_client = pymongo.MongoClient(MONGO_URI)
    mongo_db = mongo_client[MONGO_DB]

    mongo_inventory = mongo_db.inventory
    targets_collection = mongo_db.targets

    ir = get_inventory(mongo_inventory, address)

    target = targets_collection.find_one(
        {"address": address},
        {"target": True, "state": True, "config": True},
    )
    assigned_profiles = assign_profiles(ir, self.profiles, target)

    active_schedules: list[str] = []
    for period in assigned_profiles:
        task_config = generate_poll_task_definition(
            active_schedules, address, assigned_profiles, period
        )
        periodic_obj.manage_task(**task_config)

    periodic_obj.delete_unused_poll_tasks(f"{address}", active_schedules)
    # periodic_obj.delete_disabled_poll_tasks()


def generate_poll_task_definition(active_schedules, address, assigned_profiles, period):
    period_profiles = set(assigned_profiles[period])
    poll_definition = PollTaskGenerator(
        target=address, schedule_period=period, app=app, profiles=list(period_profiles)
    )
    task_config = poll_definition.generate_task_definition()
    active_schedules.append(task_config.get("name"))
    return task_config


def assign_profiles(ir, profiles, target):
    assigned_profiles: dict[int, list[str]] = {}
    address = transform_address_to_key(ir.address, ir.port)
    if ir.smart_profiles:
        for profile_name, profile in profiles.items():

            if not is_smart_profile_valid(profile_name, profile):
                continue

            # skip this profile it is static
            if profile["condition"]["type"] == "base":
                logger.debug(f"Adding base profile {profile_name}")
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
                        if "value" in cs:
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

    logger.debug(f"ir.profiles {ir.profiles}")
    logger.debug(f"profiles {profiles}")
    for profile_name in ir.profiles:
        if profile_name in profiles:
            profile = profiles[profile_name]
            if "frequency" not in profile:
                logger.warning(f"profile {profile_name} does not have frequency")
                continue
            if profile["frequency"] not in assigned_profiles:
                assigned_profiles[profile["frequency"]] = []
            assigned_profiles[profile["frequency"]].append(profile_name)
        else:
            logger.warning(
                f"profile {profile_name} was assigned for the host: {address}, no such profile in the config"
            )
    logger.debug(
        f"Profiles Assigned for host {address}: {assigned_profiles}"
    )
    return assigned_profiles


def is_smart_profile_valid(profile_name, profile):
    logger.debug(f"Checking match for {profile_name} {profile}")
    # Skip this profile its disabled
    if human_bool(profile.get("disabled", False), default=False):
        logger.debug(f"Skipping disabled profile {profile_name}")
        return False

    if "frequency" not in profile:
        logger.warning(f"Profile {profile_name} has no frequency")
        return False

    if "condition" not in profile:
        return False

    if "type" not in profile["condition"]:
        logger.warning(f"Profile {profile_name} condition has no type")
        return False

    if profile["condition"]["type"] not in ("base", "field"):
        logger.info("Profile is not smart")
        return False

    if profile["condition"]["type"] == "field" and "field" not in profile["condition"]:
        logger.warning(f"Profile {profile_name} condition has no field")
        return False

    if (
        profile["condition"]["type"] == "field"
        and "patterns" not in profile["condition"]
    ):
        logger.warning(f"Profile {profile_name} condition has no patterns")
        return False

    if profile["condition"]["type"] == "field" and not isinstance(
        profile["condition"]["patterns"], typing.List
    ):
        logger.warning(f"Patterns for profile {profile_name} must be a list")
        return False
    return True
