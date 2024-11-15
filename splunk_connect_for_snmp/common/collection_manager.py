import logging
import os
import sys
from abc import abstractmethod
from contextlib import suppress

import yaml
from celery.utils.log import get_task_logger
from jsonschema import ValidationError, validate

from splunk_connect_for_snmp.common.collections_schemas import (
    get_all_group_schemas,
    get_all_profile_schemas,
)
from splunk_connect_for_snmp.common.customised_json_formatter import (
    CustomisedJSONFormatter,
)
from splunk_connect_for_snmp.common.hummanbool import human_bool

with suppress(ImportError, OSError):
    from dotenv import load_dotenv

    load_dotenv()

CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.yaml")
CONFIG_FROM_MONGO = human_bool(os.getenv("CONFIG_FROM_MONGO", "false").lower())
celery_logger = get_task_logger(__name__)

log_level = "INFO"
formatter = CustomisedJSONFormatter()
logger = logging.getLogger(__name__)
logger.setLevel(log_level)

# writing to stdout
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(log_level)
handler.setFormatter(formatter)
logger.addHandler(handler)


class CollectionManager:
    def __init__(self, mongo, collection_name):
        self.mongo = mongo
        self.collection = getattr(mongo.sc4snmp, collection_name)

    @staticmethod
    @abstractmethod
    def gather_elements():
        pass

    @staticmethod
    @abstractmethod
    def validate_elements(elements: dict):
        pass

    def return_collection_once(self):
        collection_elements = {}
        collection_cursor = self.collection.find({}, {"_id": 0})
        for item in collection_cursor:
            collection_elements.update(item)
        return collection_elements

    def return_collection(self):
        for _ in range(3):
            collection_elements = self.return_collection_once()
            if collection_elements:
                return collection_elements
        return {}

    def return_element(self, field_name, key):
        collection_element = self.collection.find({field_name: key}, {"_id": 0})
        return collection_element

    def update_collection(self, elements):
        elements_to_insert = []
        for key, value in elements.items():
            elements_to_insert.append({key: value})
        if elements_to_insert:
            with self.mongo.start_session() as session:
                with session.start_transaction():
                    self.collection.delete_many({})
                    self.collection.insert_many(elements_to_insert)
        else:
            self.collection.delete_many({})

    def update_all(self):
        all_elements = self.gather_elements()
        # check in case only header is present
        if all_elements is None:
            all_elements = {}
        self.validate_elements(all_elements)
        self.update_collection(all_elements)


class GroupsManager(CollectionManager):
    def __init__(self, mongo):
        super().__init__(mongo, "groups")

    @staticmethod
    @abstractmethod
    def validate_elements(elements: dict):
        schemas = get_all_group_schemas()
        invalid_groups = []
        for group_name, group_body in elements.items():
            valid = False
            for schema in schemas:
                try:
                    validate(group_body, schema)
                    valid = True
                    break
                except ValidationError:
                    continue
            if not valid:
                invalid_groups.append(group_name)
        for group in invalid_groups:
            del elements[group]
        if invalid_groups:
            logger.error(
                f"The following groups have invalid configuration and won't be used: {invalid_groups}. Please check "
                f"indentation and keywords spelling inside inside mentioned groups configuration."
            )

    def gather_elements(self):
        groups = {}
        if CONFIG_FROM_MONGO:
            groups_list = list(self.mongo.sc4snmp.groups_ui.find({}, {"_id": 0}))
            for gr in groups_list:
                groups.update(gr)
        else:
            try:
                with open(CONFIG_PATH, encoding="utf-8") as file:
                    config_runtime = yaml.safe_load(file)
                    if "groups" in config_runtime:
                        groups = config_runtime.get("groups", {})
            except FileNotFoundError:
                celery_logger.info(f"File: {CONFIG_PATH} not found")
        return groups


class ProfilesManager(CollectionManager):
    def __init__(self, mongo):
        super().__init__(mongo, "profiles")

    @staticmethod
    @abstractmethod
    def validate_elements(elements: dict):
        schemas = get_all_profile_schemas()
        invalid_profiles = []
        for profile_name, profile_body in elements.items():
            valid = False
            for schema in schemas:
                try:
                    validate(profile_body, schema)
                    valid = True
                    break
                except ValidationError:
                    continue
            if not valid:
                invalid_profiles.append(profile_name)
        for profile in invalid_profiles:
            del elements[profile]
        if invalid_profiles:
            logger.error(
                f"The following profiles have invalid configuration and won't be used: {invalid_profiles}. Please check "
                f"indentation and keywords spelling inside inside mentioned profiles configuration."
            )

    def gather_elements(self):
        active_profiles = {}

        pkg_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "profiles"
        )
        for file in os.listdir(pkg_path):
            if file.endswith("yaml"):
                with open(os.path.join(pkg_path, file), encoding="utf-8") as of:
                    profiles = yaml.safe_load(of)
                    celery_logger.info(
                        f"loading {len(profiles.keys())} profiles from shared profile group {file}"
                    )
                    for key, profile in profiles.items():
                        active_profiles[key] = profile
        if CONFIG_FROM_MONGO:
            self.merge_profiles_from_ui(active_profiles)
        else:
            self.merge_profiles_from_config_file(active_profiles)
        return active_profiles

    def merge_profiles_from_config_file(self, active_profiles):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as file:
                config_runtime = yaml.safe_load(file)
                if "profiles" in config_runtime:
                    profiles = config_runtime.get("profiles", {})
                    celery_logger.info(
                        f"loading {len(profiles.keys())} profiles from runtime profile group"
                    )
                    for key, profile in profiles.items():
                        self.assign_profiles_to_dict(active_profiles, key, profile)
        except FileNotFoundError:
            celery_logger.info(f"File: {CONFIG_PATH} not found")

    @staticmethod
    def assign_profiles_to_dict(active_profiles, key, profile):
        if key in active_profiles:
            if not profile.get("enabled", True):
                celery_logger.info(f"disabling profile {key}")
                del active_profiles[key]
            else:
                active_profiles[key] = profile
        else:
            active_profiles[key] = profile

    def merge_profiles_from_ui(self, active_profiles):
        profiles_list = list(self.mongo.sc4snmp.profiles_ui.find({}, {"_id": 0}))
        for pr in profiles_list:
            key = list(pr.keys())[0]
            profile = pr[key]
            self.assign_profiles_to_dict(active_profiles, key, profile)
