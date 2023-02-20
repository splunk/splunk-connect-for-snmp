from functools import reduce
from celery.utils.log import get_task_logger
from pysnmp.smi.rfc1902 import ObjectIdentity, ObjectType

logger = get_task_logger(__name__)


class Varbind:
    def __init__(self, varbind_list):
        if isinstance(varbind_list, str):
            varbind_list = [varbind_list]
        self.list = varbind_list
        self.object_identity = ObjectType(ObjectIdentity(*varbind_list))

    def mapping_key(self):
        string_list_of_varbinds = [str(varbind) for varbind in self.list]
        return ":".join(string_list_of_varbinds)

    def __repr__(self):
        return f"{self.list}"


class VarBindContainer:
    def __init__(self):
        self.map = {}

    def add_varbind(self, varbind):
        mapping_key = varbind.mapping_key()
        if mapping_key in self.map:
            print(f"Element {mapping_key} already in the varbind container")
            return
        if len(varbind.list) > 1:
            if varbind.list[0] in self.map:
                print(
                    f"Element {mapping_key} not added as {varbind.list[0]} is already in the varbind container"
                )
                return
        if len(varbind.list) > 2:
            varbind_tmp = Varbind(varbind.list[:2])
            mapping_key_for_two = varbind_tmp.mapping_key()
            if mapping_key_for_two in self.map:
                print(
                    f"Element {mapping_key} not added as {mapping_key_for_two} is already in the varbind container"
                )
                return
        self.map[mapping_key] = varbind

    def return_varbind_keys(self):
        return list(self.map.keys())

    def return_varbind_values(self):
        return list(self.map.values())

    def get_mib_families(self):
        mib_families = []
        for varbind in self.map.values():
            mib_families.append(varbind.list[0])
        return mib_families

    def get_profile_mapping(self, profile_name):
        varbind_keys = self.return_varbind_keys()
        dict_of_keys_and_profiles = {}
        for varbind_key in varbind_keys:
            dict_of_keys_and_profiles[varbind_key] = profile_name
        return dict_of_keys_and_profiles

    def are_parents_in_map(self, varbind):
        varbind_root, varbind_field = varbind.split(":")[:2]
        current_varbinds = self.return_varbind_keys()
        return varbind_root in current_varbinds or f"{varbind_root}:{varbind_field}" in current_varbinds

    def __repr__(self):
        return f"{self.map}"

    def __add__(self, other):
        joined_maps = {}
        new_instance = VarBindContainer()
        joined_maps.update(self.map)
        joined_maps.update(other.map)
        key_list = sorted(list(joined_maps.keys()), key=len)
        for varbind_key in key_list:
            new_instance.add_varbind(joined_maps.get(varbind_key))
        return new_instance

    def return_varbinds(self):
        varbinds = []
        for varbind in self.map:
            varbinds += self.map[varbind]
        return varbinds


class Profile:
    def __init__(self, name, profile_dict):
        self.name = name
        self.type = profile_dict.get("condition", {}).get("type")
        self.frequency = profile_dict.get("frequency", None)
        self.varbinds = profile_dict.get("varBinds", None)
        self.varbinds_bulk = VarBindContainer()
        self.varbinds_get = VarBindContainer()
        self.varbinds_bulk_mapping = {}
        self.varbinds_get_mapping = {}

    def process(self):
        if self.type == "walk":
            varbind_obj = Varbind(["SNMPv2-MIB"])
            self.varbinds_bulk.add_varbind(varbind_obj)
        self.divide_on_bulk_and_get()
        if self.type != "walk":
            self.varbinds_bulk_mapping = self.varbinds_bulk.get_profile_mapping(self.name)
            self.varbinds_get_mapping = self.varbinds_get.get_profile_mapping(self.name)
        else:
            mib_families = self.get_mib_families()
            if "IF-MIB" not in mib_families:
                varbind_obj = Varbind(["IF-MIB"])
                self.varbinds_bulk.add_varbind(varbind_obj)

    def divide_on_bulk_and_get(self):
        for varbind in sorted(self.varbinds, key=len):
            varbind_obj = Varbind(varbind)
            if len(varbind) < 3:
                self.varbinds_bulk.add_varbind(varbind_obj)
            else:
                if not self.varbinds_bulk.are_parents_in_map(varbind_obj.mapping_key()):
                    self.varbinds_get.add_varbind(varbind_obj)

    def get_varbinds(self):
        return self.varbinds_bulk, self.varbinds_get

    def get_mib_families(self):
        return set(
            self.varbinds_bulk.get_mib_families() + self.varbinds_get.get_mib_families()
        )

    def return_mapping_and_varbinds(self):
        varbinds_get = [value.object_identity for value in self.varbinds_get.return_varbind_values()]
        varbinds_bulk = [value.object_identity for value in self.varbinds_bulk.return_varbind_values()]
        return varbinds_get, self.varbinds_get_mapping, varbinds_bulk, self.varbinds_bulk_mapping

    def __add__(self, other):
        new_instance = Profile(f"{self.name}:{other.name}", {})
        new_instance.varbinds_bulk = self.varbinds_bulk + other.varbinds_bulk
        new_instance.varbinds_get = self.varbinds_get + other.varbinds_get
        new_instance.varbinds_bulk_mapping = dict(self.varbinds_bulk_mapping, **other.varbinds_bulk_mapping)
        new_instance.varbinds_get_mapping = dict(self.varbinds_get_mapping, **other.varbinds_get_mapping)
        return new_instance

    def __repr__(self):
        return f"Profile: {self.name}, varbinds_get: {self.varbinds_get}, varbinds_bulk: {self.varbinds_bulk}"


class ProfileCollection:
    def __init__(self, list_of_profiles):
        self.list_of_profiles_raw = list_of_profiles
        self.list_of_profiles = {}

    def process_profiles(self):
        for profile_name, profile_body in self.list_of_profiles_raw.items():
            current_profile = Profile(profile_name, profile_body)
            current_profile.process()
            self.list_of_profiles[profile_name] = current_profile

    def get_profiles(self, profiles_names, walk=False) -> Profile:
        profiles = [self.get_profile(name) for name in profiles_names]
        if len(profiles) == 1 or walk:
            return profiles[0]
        return reduce(self.add_profiles, profiles)

    def add_profiles(self, first_profile, second_profile):
        if isinstance(first_profile, Profile) and isinstance(second_profile, Profile):
            return first_profile + second_profile
        elif isinstance(first_profile, Profile):
            return first_profile
        elif isinstance(second_profile, Profile):
            return second_profile

    def update(self, list_of_profiles):
        if self.list_of_profiles_raw == list_of_profiles:
            logger.info("No change in profiles")
        else:
            self.list_of_profiles_raw = list_of_profiles
            self.process_profiles()

    def get_profile(self, profile_name):
        if profile_name in self.list_of_profiles:
            profile = self.list_of_profiles.get(profile_name)
            if not profile.varbinds and profile.type != "walk":
                logger.warning(
                    f"or varBinds section not present inside the profile {profile_name}"
                )
                return {}
            return self.list_of_profiles.get(profile_name)
        else:
            logger.warning(
                f"There is either profile: {profile_name} missing from the configuration, or varBinds section not"
                f"present inside the profile"
            )
            return {}
