import os
from unittest import TestCase, mock
from unittest.mock import Mock

from splunk_connect_for_snmp.common.collection_manager import GroupsManager


def return_mocked_path(file_name):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "groups", file_name)


def return_yaml_groups(args=None):
    return return_mocked_path("group_config.yaml")


def return_yaml_groups_more_than_one(args=None):
    return return_mocked_path("groups_config_more_than_one")


def return_not_existing_config(*args):
    return return_mocked_path("runtime_config_that_doesnt_exist.yaml")


class TestGroups(TestCase):
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_PATH",
        return_yaml_groups(),
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
        return_yaml_groups(),
    )
    def return_yaml_groups_more_than_one(self):
        active_groups = {
            "group1": {
                "group1": [
                    {"address": "123.0.0.1", "port": 161},
                    {"address": "178.8.8.1", "port": 999},
                ]
            },
            "switches": {
                "group1": [
                    {"address": "12.22.23.33", "port": 161},
                    {"address": "1.1.1.1", "port": 162},
                ]
            },
        }
        groups_manager = GroupsManager(Mock())
        groups = groups_manager.gather_elements()
        self.assertEqual(groups, active_groups)

    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_PATH",
        return_not_existing_config(),
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
