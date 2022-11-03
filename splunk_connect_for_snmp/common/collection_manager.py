import os
from abc import abstractmethod

import yaml
from celery.utils.log import get_task_logger

try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass

CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.yaml")
CONFIG_FROM_MONGO = os.getenv("CONFIG_FROM_MONGO", "false")
logger = get_task_logger(__name__)


class CollectionManager:
    def __init__(self, mongo, collection_name):
        self.mongo = mongo
        self.collection = getattr(mongo.sc4snmp, collection_name)

    @staticmethod
    @abstractmethod
    def gather_elements():
        pass

    def return_collection_once(self):
        collection_elements = {}
        collection_cursor = self.collection.find({}, {"_id": 0})
        for item in collection_cursor:
            collection_elements.update(item)
        return collection_elements

    def return_collection(self):
        for retry in range(3):
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
        self.update_collection(all_elements)


class GroupsManager(CollectionManager):
    def __init__(self, mongo):
        super().__init__(mongo, "groups")

    #@staticmethod
    def gather_elements(self):
        groups = {}
        if CONFIG_FROM_MONGO.lower() in ["true", "1", "t"]:
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
                logger.info(f"File: {CONFIG_PATH} not found")
        return groups


class ProfilesManager(CollectionManager):
    def __init__(self, mongo):
        super().__init__(mongo, "profiles")

    #@staticmethod
    def gather_elements(self):
        active_profiles = {}

        pkg_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "profiles"
        )
        for file in os.listdir(pkg_path):
            if file.endswith("yaml"):
                with open(os.path.join(pkg_path, file), encoding="utf-8") as of:
                    profiles = yaml.safe_load(of)
                    logger.info(
                        f"loading {len(profiles.keys())} profiles from shared profile group {file}"
                    )
                    for key, profile in profiles.items():
                        active_profiles[key] = profile
        if CONFIG_FROM_MONGO.lower() in ["true", "1", "t"]:
            profiles_list = list(self.mongo.sc4snmp.profiles_ui.find({}, {"_id": 0}))
            for pr in profiles_list:
                key = list(pr.keys())[0]
                profile = pr[key]
                if key in active_profiles:
                    if not profile.get("enabled", True):
                        logger.info(f"disabling profile {key}")
                        del active_profiles[key]
                    else:
                        active_profiles[key] = profile
                else:
                    active_profiles[key] = profile
        else:
            try:
                with open(CONFIG_PATH, encoding="utf-8") as file:
                    config_runtime = yaml.safe_load(file)
                    if "profiles" in config_runtime:
                        profiles = config_runtime.get("profiles", {})
                        logger.info(
                            f"loading {len(profiles.keys())} profiles from runtime profile group"
                        )
                        for key, profile in profiles.items():
                            if key in active_profiles:
                                if not profile.get("enabled", True):
                                    logger.info(f"disabling profile {key}")
                                    del active_profiles[key]
                                else:
                                    active_profiles[key] = profile
                            else:
                                active_profiles[key] = profile
            except FileNotFoundError:
                logger.info(f"File: {CONFIG_PATH} not found")
        return active_profiles
