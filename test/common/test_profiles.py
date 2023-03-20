import os
from unittest import TestCase, mock
from unittest.mock import Mock

from splunk_connect_for_snmp.common.collection_manager import ProfilesManager


def return_mocked_path(file_name):
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "base_profiles", file_name
    )


def return_yaml_profiles(args=None):
    return [return_mocked_path("base.yaml")]


def return_yaml_empty_profiles(args=None):
    return []


def return_config_without_profiles(*args):
    return return_mocked_path("runtime_config_without_profiles.yaml")


def return_not_existing_config(*args):
    return return_mocked_path("runtime_config_that_doesnt_exist.yaml")


def return_config(*args):
    return return_mocked_path("runtime_config_with_profiles.yaml")


def return_disabled_config(*args):
    return return_mocked_path("runtime_config_enabled.yaml")


def return_not_existing_file(*args):
    return [return_mocked_path("runtime_config_that_doesnt_exist.yaml")]


class TestProfiles(TestCase):
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.os.listdir",
        return_not_existing_file,
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_PATH",
        return_config_without_profiles(),
    )
    def test_base_files_not_found(self):
        profiles_manager = ProfilesManager(Mock())
        with self.assertRaises(FileNotFoundError):
            profiles_manager.gather_elements()

    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.os.listdir",
        return_yaml_profiles,
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_PATH",
        return_not_existing_config(),
    )
    def test_config_file_not_found(self):
        with self.assertLogs(
            "splunk_connect_for_snmp.common.collection_manager", level="INFO"
        ) as cm:
            profiles_manager = ProfilesManager(Mock())
            profiles_manager.gather_elements()
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
        "splunk_connect_for_snmp.common.collection_manager.os.listdir",
        return_yaml_profiles,
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_PATH",
        return_config_without_profiles(),
    )
    def test_read_base_profiles(self):
        active_profiles = {
            "BaseUpTime": {
                "frequency": 300,
                "condition": {"type": "base"},
                "varBinds": [
                    ["IF-MIB", "ifName"],
                    ["IF-MIB", "ifAlias"],
                    ["SNMPv2-MIB", "sysUpTime", 0],
                ],
            },
            "EnrichIF": {
                "frequency": 600,
                "condition": {"type": "base"},
                "varBinds": [
                    ["IF-MIB", "ifDescr"],
                    ["IF-MIB", "ifAdminStatus"],
                    ["IF-MIB", "ifName"],
                    ["IF-MIB", "ifAlias"],
                ],
            },
        }
        profiles_manager = ProfilesManager(Mock())
        profiles = profiles_manager.gather_elements()
        self.assertEqual(profiles, active_profiles)

    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.os.listdir",
        return_yaml_empty_profiles,
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_PATH", return_config()
    )
    def test_runtime_profiles(self):
        active_profiles = {
            "test_2": {
                "frequency": 120,
                "varBinds": [
                    ["IF-MIB", "ifInDiscards", 1],
                    ["IF-MIB", "ifOutErrors"],
                    ["SNMPv2-MIB", "sysDescr", 0],
                ],
            },
            "new_profiles": {"frequency": 6, "varBinds": [["IP-MIB"]]},
            "generic_switch": {
                "frequency": 5,
                "varBinds": [
                    ["SNMPv2-MIB", "sysDescr"],
                    ["SNMPv2-MIB", "sysName", 0],
                    ["IF-MIB"],
                    ["TCP-MIB"],
                    ["UDP-MIB"],
                ],
            },
        }
        profiles_manager = ProfilesManager(Mock())
        profiles = profiles_manager.gather_elements()
        self.assertEqual(profiles, active_profiles)

    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.os.listdir",
        return_yaml_profiles,
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_PATH", return_config()
    )
    def test_all_profiles(self):
        active_profiles = {
            "BaseUpTime": {
                "frequency": 300,
                "condition": {"type": "base"},
                "varBinds": [
                    ["IF-MIB", "ifName"],
                    ["IF-MIB", "ifAlias"],
                    ["SNMPv2-MIB", "sysUpTime", 0],
                ],
            },
            "EnrichIF": {
                "frequency": 600,
                "condition": {"type": "base"},
                "varBinds": [
                    ["IF-MIB", "ifDescr"],
                    ["IF-MIB", "ifAdminStatus"],
                    ["IF-MIB", "ifName"],
                    ["IF-MIB", "ifAlias"],
                ],
            },
            "test_2": {
                "frequency": 120,
                "varBinds": [
                    ["IF-MIB", "ifInDiscards", 1],
                    ["IF-MIB", "ifOutErrors"],
                    ["SNMPv2-MIB", "sysDescr", 0],
                ],
            },
            "new_profiles": {"frequency": 6, "varBinds": [["IP-MIB"]]},
            "generic_switch": {
                "frequency": 5,
                "varBinds": [
                    ["SNMPv2-MIB", "sysDescr"],
                    ["SNMPv2-MIB", "sysName", 0],
                    ["IF-MIB"],
                    ["TCP-MIB"],
                    ["UDP-MIB"],
                ],
            },
        }
        profiles_manager = ProfilesManager(Mock())
        profiles = profiles_manager.gather_elements()
        self.assertEqual(profiles, active_profiles)

    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.os.listdir",
        return_yaml_profiles,
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_PATH",
        return_disabled_config(),
    )
    def test_disabled_profiles(self):
        active_profiles = {
            "EnrichIF": {
                "frequency": 200,
                "condition": {"type": "base"},
                "varBinds": [
                    ["IF-MIB", "ifDescr"],
                    ["IF-MIB", "ifAdminStatus"],
                    ["IF-MIB", "ifName"],
                ],
            }
        }
        profiles_manager = ProfilesManager(Mock())
        profiles = profiles_manager.gather_elements()
        self.assertEqual(profiles, active_profiles)
