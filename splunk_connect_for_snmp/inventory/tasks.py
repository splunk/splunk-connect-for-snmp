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
import typing

from splunk_connect_for_snmp.snmp.manager import get_inventory

from ..common.collection_manager import ProfilesManager
from ..common.task_generator import PollTaskGenerator
from .loader import transform_address_to_key

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


class BadlyFormattedFieldError(Exception):
    pass


class InventoryTask(Task):
    def __init__(self):
        self.mongo_client = pymongo.MongoClient(MONGO_URI)
        self.profiles_manager = ProfilesManager(self.mongo_client)
        self.profiles = self.profiles_manager.return_collection()


@shared_task(bind=True, base=InventoryTask)
def inventory_setup_poller(self, work):
    address = work["address"]
    group = work.get("group")
    self.profiles = self.profiles_manager.return_collection()
    logger.debug("Profiles reloaded")

    periodic_obj = customtaskmanager.CustomPeriodicTaskManager()

    mongo_db = self.mongo_client[MONGO_DB]

    mongo_inventory = mongo_db.inventory
    targets_collection = mongo_db.targets

    ir = get_inventory(mongo_inventory, address)

    target = targets_collection.find_one(
        {"address": address},
        {"target": True, "state": True, "config": True},
    )

    assigned_profiles, computed_conditional_profiles = assign_profiles(
        ir, self.profiles, target
    )
    for profile in computed_conditional_profiles:
        conditional_profile_name = list(profile.keys())[0]
        mongo_profile_tag = f"{list(profile.keys())[0]}__{address.replace('.', '|')}"
        profile_body = list(profile.values())[0]
        try:
            new_profile = generate_conditional_profile(
                mongo_db, mongo_profile_tag, profile_body, address
            )
        except Exception as e:
            logger.warning(f"Profile {conditional_profile_name} for {address} couldn't be processed: {e}")
            continue
        mongo_db.profiles.replace_one(
            {mongo_profile_tag: {"$exists": True}}, new_profile, upsert=True
        )
        add_profile_to_assigned_list(
            assigned_profiles, profile_body["frequency"], mongo_profile_tag
        )
    logger.debug(f"Profiles Assigned for host {address}: {assigned_profiles}")
    active_schedules: list[str] = []
    for period in assigned_profiles:
        task_config = generate_poll_task_definition(
            active_schedules, address, assigned_profiles, period, group
        )
        periodic_obj.manage_task(**task_config)

    periodic_obj.delete_unused_poll_tasks(f"{address}", active_schedules)


def generate_poll_task_definition(
    active_schedules, address, assigned_profiles, period, group=None
):
    period_profiles = set(assigned_profiles[period])
    poll_definition = PollTaskGenerator(
        target=address,
        schedule_period=period,
        app=app,
        host_group=group,
        profiles=list(period_profiles),
    )
    task_config = poll_definition.generate_task_definition()
    active_schedules.append(task_config.get("name"))
    return task_config


def add_profile_to_assigned_list(
    assigned_profiles: dict[int, list[str]], frequency: int, profile_name: str
):
    if frequency not in assigned_profiles:
        assigned_profiles[frequency] = []
    assigned_profiles[frequency].append(profile_name)


def assign_profiles(ir, profiles, target):
    assigned_profiles: dict[int, list[str]] = {}
    address = transform_address_to_key(ir.address, ir.port)
    computed_profiles = []
    if ir.smart_profiles:
        for profile_name, profile in profiles.items():

            if not is_smart_profile_valid(profile_name, profile):
                continue

            # skip this profile it is static
            if profile["condition"]["type"] == "base":
                logger.debug(f"Adding base profile {profile_name}")
                add_profile_to_assigned_list(
                    assigned_profiles, profile["frequency"], profile_name
                )

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
                                    add_profile_to_assigned_list(
                                        assigned_profiles,
                                        profile["frequency"],
                                        profile_name,
                                    )
                                    continue

    logger.debug(f"ir.profiles {ir.profiles}")
    logger.debug(f"profiles {profiles}")
    for profile_name in ir.profiles:
        if profile_name in profiles:
            profile = profiles[profile_name]
            if "condition" in profile:
                if profile["condition"].get("type") == "walk":
                    logger.warning(
                        f"profile {profile_name} is a walk profile, it cannot be used as a static profile"
                    )
                    continue
                logger.warning(
                    f"profile {profile_name} is a smart profile, it does not need to be configured as a static one"
                )
            elif "conditions" in profile:
                computed_profiles.append({profile_name: profile})
                continue
            if "frequency" not in profile:
                logger.warning(f"profile {profile_name} does not have frequency")
                continue
            add_profile_to_assigned_list(
                assigned_profiles, profile["frequency"], profile_name
            )
        else:
            logger.warning(
                f"profile {profile_name} was assigned for the host: {address}, no such profile in the config"
            )

    mandatory_profiles = [
        (profile_name, profile.get("frequency"))
        for profile_name, profile in profiles.items()
        if profile.get("condition", {}).get("type") == "mandatory"
    ]
    for m_profile_name, m_profile_frequency in mandatory_profiles:
        add_profile_to_assigned_list(
            assigned_profiles, m_profile_frequency, m_profile_name
        )

    return assigned_profiles, computed_profiles


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


def filter_condition_on_database(mongo_client, address: str, conditions: list):
    attributes = mongo_client.attributes
    query = create_query(conditions, address)
    result = attributes.find(
        query, {"address": 1, "group_key_hash": 1, "_id": 0, "indexes": 1}
    )
    return list(result)


def create_profile(profile_name, frequency, varBinds, records):
    # Connecting general fields from varBinds with filtered object indexes
    # like ["IF-MIB", "ifDescr"] + [1] = ["IF-MIB", "ifDescr", 1]
    varbind_list = [
        varbind + record["indexes"] for record in records for varbind in varBinds if len(varbind) == 2
    ]
    profile = {profile_name: {"frequency": frequency, "varBinds": varbind_list}}
    return profile


def create_query(conditions: typing.List[dict], address: str) -> dict:

    conditional_profiles_mapping = {
        "equals": "$eq",
        "gt": "$gt",
        "lt": "$lt",
        "in": "$in",
    }

    def _parse_mib_component(field: str) -> str:
        mib_component = field.split("|")
        if len(mib_component) < 2:
            raise BadlyFormattedFieldError(f"Field {field} is badly formatted")
        return mib_component[0]

    def _convert_to_float(value: typing.Any, ignore_error=False) -> typing.Any:
        try:
            return float(value)
        except ValueError:
            if ignore_error:
                return value
            else:
                raise BadlyFormattedFieldError(f"Value '{value}' should be numeric")

    def _get_value_for_operation(operation: str, value: str) -> typing.Any:
        if operation in ["lt", "gt"]:
            return _convert_to_float(value)
        elif operation == "in":
            return [_convert_to_float(v, True) for v in value]
        return value

    filters = []
    field = ""
    for condition in conditions:
        field = condition["field"]
        # fields in databases are written in convention "IF-MIB|ifInOctets"
        field = field.replace(".", "|")
        value = condition["value"]
        operation = condition["operation"].lower()
        value_for_querying = _get_value_for_operation(operation, value)
        mongo_operation = conditional_profiles_mapping.get(operation)
        filters.append({f"fields.{field}.value": {mongo_operation: value_for_querying}})
    mib_component = _parse_mib_component(field)
    return {
        "$and": [
            {"address": address},
            {"group_key_hash": {"$regex": f"^{mib_component}"}},
            *filters,
        ]
    }


def generate_conditional_profile(
    mongo_client, profile_name, conditional_profile_body, address
):
    profile_conditions = conditional_profile_body.get("conditions")
    profile_varbinds = conditional_profile_body.get("varBinds")
    profile_frequency = conditional_profile_body.get("frequency")
    if not profile_varbinds:
        raise BadlyFormattedFieldError(
            f"No varBinds provided in the profile"
        )
    filtered_snmp_objects = filter_condition_on_database(
        mongo_client, address, profile_conditions
    )
    new_conditional_profile = create_profile(
        profile_name, profile_frequency, profile_varbinds, filtered_snmp_objects
    )
    return new_conditional_profile
