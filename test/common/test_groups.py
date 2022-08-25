import os
from unittest import TestCase, mock
from unittest.mock import Mock

from splunk_connect_for_snmp.common.collection_manager import GroupsManager


def return_mocked_path(file_name):
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "groups", file_name
    )


def return_yaml_groups(args=None):
    return return_mocked_path("group_config.yaml")


def return_yaml_groups_more_than_one(args=None):
    return return_mocked_path("group_config.yaml")


class TestGroups(TestCase):

    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_PATH",
        return_yaml_groups(),
    )
    def test_read_one_group(self):
        active_groups = {
            "group1": ["123.0.0.1:161", "178.8.8.1:999"]
        }
        groups_manager = GroupsManager(Mock())
        groups = groups_manager.gather_elements()
        self.assertEqual(groups, active_groups)

    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_PATH",
        return_yaml_groups(),
    )
    def test_read_one_group(self):
        active_groups = {
            "group1": ["123.0.0.1:161", "178.8.8.1:999"]
        }
        groups_manager = GroupsManager(Mock())
        groups = groups_manager.gather_elements()
        self.assertEqual(groups, active_groups)
