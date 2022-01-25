from unittest import TestCase

from splunk_connect_for_snmp.common.inventory_record import InventoryRecord
from splunk_connect_for_snmp.inventory.tasks import assign_profiles

ir_smart = InventoryRecord.from_dict(
    {
        "address": "192.168.0.1",
        "port": "34",
        "version": "2c",
        "community": "public",
        "secret": "secret",
        "securityEngine": "ENGINE",
        "walk_interval": 1850,
        "profiles": "",
        "SmartProfiles": True,
        "delete": False,
    }
)

simple_profiles = {
    "BaseUpTime": {
        "frequency": 60,
        "condition": {
            "type": "field",
            "field": "SNMPv2-MIB.sysDescr",
            "patterns": ["^MIKROTIK"],
        },
    }
}


class TestProfilesAssignment(TestCase):
    def test_assignment_of_static_profiles(self):
        profiles = {
            "profile1": {"frequency": 20},
            "profile2": {"frequency": 30},
            "profile3": {},
        }

        ir = InventoryRecord.from_dict(
            {
                "address": "192.168.0.1",
                "port": "34",
                "version": "2c",
                "community": "public",
                "secret": "secret",
                "securityEngine": "ENGINE",
                "walk_interval": 1850,
                "profiles": "profile1;profile2;profile3;profile4",
                "SmartProfiles": False,
                "delete": False,
            }
        )

        result = assign_profiles(ir, profiles, {})
        self.assertEqual({20: ["profile1"], 30: ["profile2"]}, result)

    def test_assignment_of_base_profiles(self):
        profiles = {
            "BaseUpTime": {"frequency": 60, "condition": {"type": "base"}},
            "profile2": {"frequency": 30, "condition": {"type": "base"}},
        }

        result = assign_profiles(ir_smart, profiles, {})
        self.assertEqual({60: ["BaseUpTime"], 30: ["profile2"]}, result)

    def test_assignment_of_field_profiles(self):
        profiles = {
            "BaseUpTime": {
                "frequency": 60,
                "condition": {
                    "type": "field",
                    "field": "SNMPv2-MIB.sysDescr",
                    "patterns": ["^MIKROTIK"],
                },
            },
            "MyProfile": {
                "frequency": 60,
                "condition": {
                    "type": "field",
                    "field": "SNMPv2-MIB.sysName",
                    "patterns": ["Debian"],
                },
            },
            "OtherProfile": {
                "frequency": 60,
                "condition": {
                    "type": "field",
                    "field": "SNMPv2-MIB.sysContact",
                    "patterns": ["@splunk"],
                },
            },
        }

        target = {
            "state": {
                "SNMPv2-MIB|sysDescr": {"value": "MIKROTIK"},
                "SNMPv2-MIB|sysName": {"value": "Linux Debian 2.0.1"},
                "SNMPv2-MIB|sysContact": {"value": "non-existing-name@splunk"},
            }
        }

        result = assign_profiles(ir_smart, profiles, target)
        self.assertEqual({60: ["BaseUpTime", "MyProfile", "OtherProfile"]}, result)

    def test_assignment_of_field_profiles_missing_state(self):
        result = assign_profiles(ir_smart, simple_profiles, {})
        self.assertEqual({}, result)

    def test_assignment_of_field_profiles_db_missing_field_value(self):
        target = {"state": {"SNMPv2-MIB|sysDescr": {}}}

        result = assign_profiles(ir_smart, simple_profiles, target)
        self.assertEqual({}, result)

    def test_assignment_of_field_not_matching_regex(self):
        target = {"state": {"SNMPv2-MIB|sysDescr": {"value": "WRONG"}}}

        result = assign_profiles(ir_smart, simple_profiles, target)
        self.assertEqual({}, result)

    def test_assignment_of_static_and_smart_profiles(self):
        profiles = {
            "profile1": {"frequency": 20},
            "profile2": {"frequency": 30},
            "BaseUpTime": {"frequency": 60, "condition": {"type": "base"}},
            "profile5": {"frequency": 30, "condition": {"type": "base"}},
        }

        ir = InventoryRecord.from_dict(
            {
                "address": "192.168.0.1",
                "port": "34",
                "version": "2c",
                "community": "public",
                "secret": "secret",
                "securityEngine": "ENGINE",
                "walk_interval": 1850,
                "profiles": "profile1;profile2;",
                "SmartProfiles": True,
                "delete": False,
            }
        )

        result = assign_profiles(ir, profiles, {})
        self.assertEqual(
            {60: ["BaseUpTime"], 30: ["profile5", "profile2"], 20: ["profile1"]}, result
        )
