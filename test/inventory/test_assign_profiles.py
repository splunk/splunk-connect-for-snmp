from unittest import TestCase

from splunk_connect_for_snmp.common.inventory_record import InventoryRecord
from splunk_connect_for_snmp.inventory.tasks import assign_profiles


class TestProfilesAssignment(TestCase):
    def test_assignment_of_static_profiles(self):
        profiles = {"profile1": {"frequency": 20}, "profile2": {"frequency": 30}, "profile3": {}}

        ir = InventoryRecord.from_dict({
            "address": "192.168.0.1",
            "port": "34",
            "version": "2c",
            "community": "public",
            "secret": "secret",
            "securityEngine": "ENGINE",
            "walk_interval": 1850,
            "profiles": "profile1;profile2",
            "SmartProfiles": False,
            "delete": False,
        })

        target = {}

        result = assign_profiles(ir, profiles, target)
        self.assertEqual({20: ['profile1'], 30: ['profile2']}, result)

    def test_assignment_of_static_profiles_unknown_profile(self):
        pass

    def test_assignment_of_base_profiles(self):
        pass

    def test_assignment_of_field_profiles(self):
        pass

    def test_assignment_of_field_profiles_missing_state(self):
        pass

    def test_assignment_of_field_profiles_db_missing_field_value(self):
        pass

    def test_assignment_of_field_not_matching_regex(self):
        pass

    def test_assignment_of_field_missing_patterns(self):
        pass

    def test_assignment_of_static_and_smart_profiles(self):
        pass
