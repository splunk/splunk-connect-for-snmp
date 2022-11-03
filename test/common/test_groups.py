import os
from unittest import TestCase, mock
from unittest.mock import Mock
from bson import ObjectId

from splunk_connect_for_snmp.common.collection_manager import GroupsManager


def return_mocked_path(file_name):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "groups", file_name)


def return_yaml_groups(args=None):
    return return_mocked_path("group_config.yaml")


def return_yaml_groups_more_than_one(args=None):
    return return_mocked_path("groups_config_more_than_one.yaml")


def return_not_existing_config(*args):
    return return_mocked_path("runtime_config_that_doesnt_exist.yaml")


def mocked_inventory_from_value(value):
    return value


class TestGroups(TestCase):
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_PATH",
        return_yaml_groups(),
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_FROM_MONGO",
        "false",
    )
    def test_read_one_group(self):
        active_groups = {
            "group1": [
                {"address": "123.0.0.1", "port": 161},
                {"address": "178.8.8.1", "port": 999},
            ]
        }
        groups_manager = GroupsManager(Mock())
        groups = groups_manager.gather_elements()
        self.assertEqual(groups, active_groups)

    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_PATH",
        return_yaml_groups_more_than_one(),
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_FROM_MONGO",
        "false",
    )
    def test_return_yaml_groups_more_than_one(self):
        active_groups = {
            "group1": [
                    {"address": "123.0.0.1", "port": 161},
                    {"address": "178.8.8.1", "port": 999},
                ],
            "switches": [
                    {"address": "12.22.23.23", "port": 33},
                    {"address": "1.1.1.1", "port": 162},
                ],
        }
        groups_manager = GroupsManager(Mock())
        groups = groups_manager.gather_elements()
        self.assertEqual(groups, active_groups)

    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_PATH",
        return_not_existing_config(),
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_FROM_MONGO",
        "false",
    )
    def test_base_files_not_found(self):
        with self.assertLogs(
            "splunk_connect_for_snmp.common.collection_manager", level="INFO"
        ) as cm:
            groups_manager = GroupsManager(Mock())
            groups_manager.gather_elements()
            self.assertTrue(
                any(
                    [
                        el
                        for el in cm.output
                        if "runtime_config_that_doesnt_exist.yaml not found" in el
                    ]
                )
            )

    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_PATH",
        return_yaml_groups(),
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_FROM_MONGO",
        "true",
    )
    def test_groups_from_mongo(self):
        active_groups = {
            "group1": [
                {"address": "123.0.0.1", "port": 161},
                {"address": "178.8.8.1", "port": 999},
            ],
            "switches": [
                {"address": "12.22.23.23", "port": 33},
                {"address": "1.1.1.1", "port": 162},
            ],
        }
        mongo_mock = Mock()
        mongo_mock.sc4snmp.groups_ui.find.return_value = [
            {
                "group1": [
                    {"address": "123.0.0.1", "port": 161},
                    {"address": "178.8.8.1", "port": 999},
                ]
            },
            {
                "switches": [
                    {"address": "12.22.23.23", "port": 33},
                    {"address": "1.1.1.1", "port": 162},
                ]
            }
        ]
        groups_manager = GroupsManager(mongo_mock)
        groups = groups_manager.gather_elements()
        self.assertEqual(groups, active_groups)
