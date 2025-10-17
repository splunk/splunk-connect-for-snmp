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
from contextlib import suppress

from splunk_connect_for_snmp.snmp.manager import get_inventory

from ..common.collection_manager import ProfilesManager
from ..common.task_generator import PollTaskGenerator
from .loader import transform_address_to_key

with suppress(ImportError, OSError):
    from dotenv import load_dotenv

    load_dotenv()

import os
import re

import pymongo
import urllib3
from celery import Task, shared_task
from celery.utils.log import get_task_logger

from splunk_connect_for_snmp import customtaskmanager
from splunk_connect_for_snmp.common.hummanbool import (
    BadlyFormattedFieldError,
    convert_to_float,
    human_bool,
)

from ..poller import app

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  # nosemgrep

logger = get_task_logger(__name__)

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "sc4snmp")
CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.yaml")
PROFILES_RELOAD_DELAY = int(os.getenv("PROFILES_RELOAD_DELAY", "300"))
POLL_BASE_PROFILES = human_bool(os.getenv("POLL_BASE_PROFILES", "true"))


class InventoryTask(Task):
    def __init__(self):
        self.mongo_client = pymongo.MongoClient(MONGO_URI)
        self.profiles_manager = ProfilesManager(self.mongo_client)
        self.profiles = self.profiles_manager.return_collection()


@shared_task(bind=True, base=InventoryTask)
def inventory_setup_poller(self, work):
    address = work["address"]
    group = work.get("group")
    chain_of_tasks_expiry_time = work.get("chain_of_tasks_expiry_time")
    self.profiles = self.profiles_manager.return_collection()
    logger.debug("Profiles reloaded")

    periodic_obj = customtaskmanager.CustomPeriodicTaskManager()

    mongo_db = self.mongo_client[MONGO_DB]
    logger.info(f" === inventory_setup_poller, work={work} ===")

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
            logger.warning(
                f"Profile {conditional_profile_name} for {address} couldn't be processed: {e}"
            )
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
            active_schedules,
            address,
            assigned_profiles,
            period,
            chain_of_tasks_expiry_time,
            group,
        )
        periodic_obj.manage_task(**task_config)

    periodic_obj.delete_unused_poll_tasks(f"{address}", active_schedules)


def generate_poll_task_definition(
    active_schedules,
    address,
    assigned_profiles,
    period,
    chain_of_tasks_expiry_time,
    group=None,
):
    period_profiles = set(assigned_profiles[period])
    poll_definition = PollTaskGenerator(
        target=address,
        schedule_period=period,
        app=app,
        host_group=group,
        chain_of_tasks_expiry_time=chain_of_tasks_expiry_time,
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
    assign_smart_profiles(assigned_profiles, ir, profiles, target)

    logger.debug(f"ir.profiles {ir.profiles}")
    logger.debug(f"profiles {profiles}")
    check_profiles_type(address, assigned_profiles, computed_profiles, ir, profiles)

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


def check_profiles_type(address, assigned_profiles, computed_profiles, ir, profiles):
    for profile_name in ir.profiles:
        if profile_name in profiles:
            profile = profiles[profile_name]
            if "condition" in profile:
                if profile["condition"].get("type") == "walk":
                    logger.info(
                        f"profile {profile_name} is a walk profile, it cannot be used as a static profile"
                    )
                    continue
                logger.info(
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


def assign_smart_profiles(assigned_profiles, ir, profiles, target):
    if ir.smart_profiles:
        for profile_name, profile in profiles.items():

            if not is_smart_profile_valid(profile_name, profile):
                continue

            # skip this profile it is static
            if profile["condition"]["type"] == "base" and POLL_BASE_PROFILES:
                logger.debug(f"Adding base profile {profile_name}")
                add_profile_to_assigned_list(
                    assigned_profiles, profile["frequency"], profile_name
                )

            elif profile["condition"]["type"] == "field":
                logger.debug(f"profile is a field condition {profile_name}")
                assign_field_smart_profile(
                    assigned_profiles, profile, profile_name, target
                )


def assign_field_smart_profile(assigned_profiles, profile, profile_name, target):
    if "state" in target and (
        profile["condition"]["field"].replace(".", "|") in target["state"]
    ):
        cs = target["state"][profile["condition"]["field"].replace(".", "|")]
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


def is_smart_profile_valid(profile_name, profile):
    logger.debug(f"Checking match for {profile_name} {profile}")
    # Skip this profile its disabled
    if human_bool(profile.get("disabled", False), default=False):
        logger.debug(f"Skipping disabled profile {profile_name}")
        return False

    if "frequency" not in profile:
        logger.info(f"Profile {profile_name} has no frequency")
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


def create_profile(profile_name, frequency, varbinds, records):
    # Connecting general fields from varBinds with filtered object indexes
    # like ["IF-MIB", "ifDescr"] + [1] = ["IF-MIB", "ifDescr", 1]
    varbind_list = [
        varbind + record["indexes"]
        for record in records
        for varbind in varbinds
        if len(varbind) == 2
    ]
    profile = {profile_name: {"frequency": frequency, "varBinds": varbind_list}}
    return profile


def create_query(conditions: typing.List[dict], address: str) -> dict:
    # Define mappings for conditional and negative profiles
    profile_mappings = {
        "positive": {
            "equals": "$eq",
            "gt": "$gt",
            "lt": "$lt",
            "in": "$in",
            "regex": "$regex",
        },
        "negative": {
            "equals": "$ne",
            "gt": "$lte",
            "lt": "$gte",
            "in": "$nin",
            "regex": "$regex",
        },
    }

    # Helper functions
    def _parse_mib_component(field: str) -> str:
        components = field.split("|")
        if len(components) < 2:
            raise BadlyFormattedFieldError(f"Field {field} is badly formatted")
        return components[0]

    def _prepare_regex(value: str) -> typing.Union[list, str]:
        pattern = value.strip("/").split("/")
        return pattern if len(pattern) > 1 else pattern[0]

    def _get_value_for_operation(operation: str, value: typing.Any) -> typing.Any:
        operation_handlers = {
            "lt": lambda v: convert_to_float(v),
            "gt": lambda v: convert_to_float(v),
            "in": lambda v: [convert_to_float(item, True) for item in v],
            "regex": lambda v: _prepare_regex(v),
        }
        return operation_handlers.get(operation, lambda v: v)(value)

    def _prepare_query_input(
        operation: str, value: typing.Any, field: str, negate: bool, mongo_op: str
    ) -> dict:
        query = (
            {mongo_op: value}
            if not (operation == "regex" and isinstance(value, list))
            else {mongo_op: value[0], "$options": value[1]}
        )
        if operation == "regex" and negate:
            query = {"$not": query}
        return {f"fields.{field}.value": query}

    # Main processing loop
    filters = []
    for condition in conditions:
        field = condition["field"].replace(".", "|")  # Standardize field format
        value = condition["value"]
        negate = human_bool(condition.get("negate_operation", False), default=False)
        operation = condition["operation"].lower()

        # Determine MongoDB operator and prepare query
        mongo_op = profile_mappings["negative" if negate else "positive"].get(
            operation, ""
        )
        value_for_query = _get_value_for_operation(operation, value)
        query = _prepare_query_input(
            operation, value_for_query, field, negate, mongo_op
        )
        filters.append(query)

    # Parse MIB component for address matching
    mib_component = _parse_mib_component(field)

    # Construct final query
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
        raise BadlyFormattedFieldError("No varBinds provided in the profile")
    filtered_snmp_objects = filter_condition_on_database(
        mongo_client, address, profile_conditions
    )
    new_conditional_profile = create_profile(
        profile_name, profile_frequency, profile_varbinds, filtered_snmp_objects
    )
    return new_conditional_profile
