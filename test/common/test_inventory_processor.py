import os
from unittest import TestCase, mock
from unittest.mock import Mock, mock_open, patch

from splunk_connect_for_snmp.common.inventory_processor import (
    InventoryProcessor,
    InventoryRecordManager,
    return_hosts_from_deleted_groups,
    transform_address_to_key,
    transform_key_to_address,
)

mock_inventory_only_address = """address
54.234.85.76"""

mock_inventory_host_same_as_in_group = """address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
group1,,2c,public,,,1805,group_profile,False,False
0.0.0.0,,2c,public,,,1805,solo_profile1,False,False
0.0.0.0,1161,2c,public,,,1805,solo_profile2,False,False"""


class TestInventoryProcessor(TestCase):
    profiles = {
        "test5": {"frequency": 6, "varBinds": [["IP-MIB"]]},
        "test_33": {
            "condition": {"type": "walk"},
            "frequency": 77,
            "varBinds": [["UDP-MIB"]],
        },
        "generic_switch": {"frequency": 5, "varBinds": [["TCP-MIB"]]},
        "walk1": {
            "condition": {"type": "walk"},
            "varBinds": [["IP-MIB"], ["SNMPv2-MIB"], ["TCP-MIB"]],
        },
        "test_auto": {
            "frequency": 30,
            "condition": {
                "type": "field",
                "field": "SNMPv2-MIB.sysDescr",
                "patterns": ["1234"],
            },
            "varBinds": [["SNMPv2-MIB", "sysContact"]],
        },
    }

    def test_transform_key_to_address(self):
        self.assertEqual(("123.0.0.1", 777), transform_key_to_address("123.0.0.1:777"))
        self.assertEqual(("123.0.0.1", 161), transform_key_to_address("123.0.0.1:161"))
        self.assertEqual(("123.0.0.1", 161), transform_key_to_address("123.0.0.1"))

    def test_transform_address_to_key(self):
        self.assertEqual(transform_address_to_key("127.0.0.1", 333), "127.0.0.1:333")
        self.assertEqual(transform_address_to_key("127.0.0.1", 161), "127.0.0.1")

    def test_return_hosts_from_deleted_groups_one_host(self):
        previous_groups = {
            "group1": [
                {"address": "123.0.0.1", "port": 161},
                {"address": "178.8.8.1", "port": 999},
            ],
            "switches": [
                {"address": "12.22.23.33", "port": 161},
                {"address": "1.1.1.1", "port": 162},
            ],
        }
        new_groups = {
            "group1": [
                {"address": "123.0.0.1", "port": 161},
                {"address": "178.8.8.1", "port": 999},
            ],
            "switches": [{"address": "12.22.23.33", "port": 161}],
        }

        self.assertEqual(
            return_hosts_from_deleted_groups(previous_groups, new_groups),
            ["1.1.1.1:162"],
        )

    def test_return_hosts_from_deleted_groups_whole_group(self):
        previous_groups = {
            "group1": [
                {"address": "123.0.0.1", "port": 161},
                {"address": "178.8.8.1", "port": 999},
            ],
            "switches": [
                {"address": "12.22.23.33", "port": 161},
                {"address": "1.1.1.1", "port": 162},
            ],
        }
        new_groups = {
            "group1": [
                {"address": "123.0.0.1", "port": 161},
                {"address": "178.8.8.1", "port": 999},
            ],
        }

        self.assertEqual(
            return_hosts_from_deleted_groups(previous_groups, new_groups),
            ["12.22.23.33", "1.1.1.1:162"],
        )

    def test_return_hosts_from_deleted_groups_one_host_and_group(self):
        previous_groups = {
            "group1": [
                {"address": "123.0.0.1", "port": 161},
                {"address": "178.8.8.1", "port": 999},
            ],
            "switches": [
                {"address": "12.22.23.33", "port": 161},
                {"address": "1.1.1.1", "port": 162},
            ],
        }
        new_groups = {
            "switches": [{"address": "12.22.23.33"}],
        }

        self.assertEqual(
            return_hosts_from_deleted_groups(previous_groups, new_groups),
            ["123.0.0.1", "178.8.8.1:999", "1.1.1.1:162"],
        )

    def test_return_hosts_empty(self):
        previous_groups = {}
        new_groups = {}
        self.assertEqual(
            return_hosts_from_deleted_groups(previous_groups, new_groups), []
        )

    def test_return_hosts_new_ones(self):
        previous_groups = {}
        new_groups = {"switches": [{"address": "12.22.23.33", "port": 161}]}
        self.assertEqual(
            return_hosts_from_deleted_groups(previous_groups, new_groups), []
        )

    def test_get_group_hosts(self):
        group_manager = Mock()
        group_object = {
            "address": "group1",
            "port": "",
            "version": "2c",
            "community": "public",
            "secret": "",
            "securityEngine": "",
            "walk_interval": "788",
            "profiles": "walk1;generic_switch",
            "SmartProfiles": "f",
            "delete": "",
        }
        group_object_returned = [
            {
                "address": "123.0.0.1",
                "port": 161,
                "version": "2c",
                "community": "public",
                "secret": "",
                "securityEngine": "",
                "walk_interval": "788",
                "profiles": "walk1;generic_switch",
                "SmartProfiles": "f",
                "group": "group1",
                "delete": "",
            },
            {
                "address": "178.8.8.1",
                "port": 999,
                "version": "2c",
                "community": "public",
                "secret": "",
                "securityEngine": "",
                "walk_interval": "788",
                "profiles": "walk1;generic_switch",
                "SmartProfiles": "f",
                "group": "group1",
                "delete": "",
            },
        ]
        inventory_processor = InventoryProcessor(group_manager, Mock())
        group_manager.return_element.return_value = [
            {
                "group1": [
                    {"address": "123.0.0.1", "port": 161},
                    {"address": "178.8.8.1", "port": 999},
                ]
            }
        ]
        inventory_processor.get_group_hosts(group_object, "group1")
        self.assertListEqual(
            inventory_processor.inventory_records, group_object_returned
        )

    def test_get_group_hosts_no_group_found(self):
        group_manager = Mock()
        logger = Mock()
        group_object = {
            "address": "group1",
            "port": "",
            "version": "2c",
            "community": "public",
            "secret": "",
            "securityEngine": "",
            "walk_interval": "788",
            "profiles": "walk1;generic_switch",
            "SmartProfiles": "f",
            "delete": "",
        }
        inventory_processor = InventoryProcessor(group_manager, logger)
        group_manager.return_element.return_value = []
        inventory_processor.get_group_hosts(group_object, "group1")
        logger.warning.assert_called_with(
            "Group group1 doesn't exist in the configuration. Skipping..."
        )

    def test_process_line_comment(self):
        logger = Mock()
        source_record = {"address": "#54.234.85.76"}
        inventory_processor = InventoryProcessor(Mock(), logger)
        inventory_processor.process_line(source_record)
        logger.warning.assert_called_with(
            "Record: #54.234.85.76 is commented out. Skipping..."
        )

    @patch(
        "builtins.open", new_callable=mock_open, read_data=mock_inventory_only_address
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.inventory_processor.INVENTORY_FROM_MONGO",
        "false",
    )
    def test_process_line_host(self, m_inventory):
        source_record = {"address": "54.234.85.76"}
        inventory_processor = InventoryProcessor(Mock(), Mock())
        inventory_processor.get_all_hosts()
        self.assertEqual(inventory_processor.inventory_records, [source_record])

    def test_process_line_group(self):
        source_record = {"address": "group1"}
        inventory_processor = InventoryProcessor(Mock(), Mock())
        inventory_processor.get_group_hosts = Mock()
        inventory_processor.process_line(source_record)
        inventory_processor.get_group_hosts.assert_called_with(source_record, "group1")

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data=mock_inventory_host_same_as_in_group,
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.inventory_processor.INVENTORY_FROM_MONGO",
        "false",
    )
    def test_ignore_line_host_configured_in_group(self, m_load_element):
        returned_group = [
            {
                "group1": [
                    {"address": "0.0.0.0", "port": "161"},
                    {"address": "127.0.0.1", "port": "161"},
                ]
            }
        ]
        group_manager = Mock()
        group_manager.return_element.return_value = returned_group
        inventory_processor = InventoryProcessor(group_manager, Mock())
        expected = [
            {
                "address": "0.0.0.0",
                "port": "161",
                "version": "2c",
                "community": "public",
                "secret": "",
                "security_engine": "",
                "walk_interval": "1805",
                "profiles": "group_profile",
                "smart_profiles": "False",
                "delete": "False",
                "group": "group1",
            },
            {
                "address": "127.0.0.1",
                "port": "161",
                "version": "2c",
                "community": "public",
                "secret": "",
                "security_engine": "",
                "walk_interval": "1805",
                "profiles": "group_profile",
                "smart_profiles": "False",
                "delete": "False",
                "group": "group1",
            },
            {
                "address": "0.0.0.0",
                "port": "1161",
                "version": "2c",
                "community": "public",
                "secret": "",
                "security_engine": "",
                "walk_interval": "1805",
                "profiles": "solo_profile2",
                "smart_profiles": "False",
                "delete": "False",
            },
        ]
        inventory_processor.get_all_hosts()
        self.assertEqual(expected, inventory_processor.inventory_records)

    def test_return_walk_profile(self):
        inventory_profiles = ["walk1", "generic_switch"]
        inventory_record_manager = InventoryRecordManager(Mock(), Mock(), Mock())
        self.assertEqual(
            inventory_record_manager.return_walk_profile(
                self.profiles, inventory_profiles
            ),
            "walk1",
        )

    def test_return_walk_profile_more_than_one(self):
        inventory_profiles = ["walk1", "test_33", "generic_switch"]
        inventory_record_manager = InventoryRecordManager(Mock(), Mock(), Mock())
        self.assertEqual(
            inventory_record_manager.return_walk_profile(
                self.profiles, inventory_profiles
            ),
            "test_33",
        )

    def test_return_walk_profile_no_walk_in_inventory(self):
        inventory_profiles = ["generic_switch"]
        inventory_record_manager = InventoryRecordManager(Mock(), Mock(), Mock())
        self.assertEqual(
            inventory_record_manager.return_walk_profile(
                self.profiles, inventory_profiles
            ),
            None,
        )

    def test_return_walk_profile_no_walk_in_config(self):
        inventory_profiles = ["generic_switch", "walk2"]
        inventory_record_manager = InventoryRecordManager(Mock(), Mock(), Mock())
        self.assertEqual(
            inventory_record_manager.return_walk_profile(
                self.profiles, inventory_profiles
            ),
            None,
        )

    def test_return_walk_profile_no_config(self):
        inventory_profiles = ["generic_switch", "walk2"]
        inventory_record_manager = InventoryRecordManager(Mock(), Mock(), Mock())
        self.assertEqual(
            inventory_record_manager.return_walk_profile({}, inventory_profiles), None
        )

    def test_return_walk_profile_no_config_no_inventory(self):
        inventory_profiles = []
        inventory_record_manager = InventoryRecordManager(Mock(), Mock(), Mock())
        self.assertEqual(
            inventory_record_manager.return_walk_profile({}, inventory_profiles), None
        )

    def test_return_walk_profile_no_inventory(self):
        inventory_record_manager = InventoryRecordManager(Mock(), Mock(), Mock())
        self.assertEqual(
            inventory_record_manager.return_walk_profile(self.profiles, []), None
        )
