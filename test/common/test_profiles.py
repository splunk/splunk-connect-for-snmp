import os
from unittest import TestCase, mock
from unittest.mock import Mock

import pytest

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


@pytest.mark.parametrize(
    "frequency,valid",
    [
        (-1, False),
        (0, False),
        (1, False),
        (3, False),
        (4, False),
        (4.9, False),
        (5.5, False),
        ("5", False),
        (True, False),
        (False, False),
        (None, False),
        ([], False),
        ({}, False),
        (5, True),
        (5.0, True),
        (6, True),
        (6.0, True),
    ],
)
@pytest.mark.parametrize(
    "profile_settings",
    [
        {},
        {"condition": {"type": "base"}},
        {"condition": {"type": "mandatory"}},
        {
            "condition": {
                "type": "field",
                "field": "SNMPv2-MIB.sysDescr",
                "patterns": ["Linux.*"],
            }
        },
        {
            "conditions": [
                {
                    "field": "IF-MIB.ifAdminStatus",
                    "operation": "equals",
                    "value": "up",
                }
            ]
        },
    ],
    ids=["standard", "base", "mandatory", "smart", "conditional"],
)
def test_profile_frequency_minimum(frequency, valid, profile_settings):
    profile = {
        "frequency": frequency,
        "varBinds": [["SNMPv2-MIB", "sysUpTime", 0]],
        **profile_settings,
    }
    valid_profile = {**profile, "frequency": 10}
    profiles = {"selected": profile, "valid": valid_profile}

    ProfilesManager.validate_elements(profiles)

    expected = {"valid": valid_profile}
    if valid:
        expected["selected"] = profile
    assert profiles == expected


@pytest.mark.parametrize(
    "frequency", [-1, 0, 1, 3, 4, 4.9, 5.5, "5", True, False, None, [], {}]
)
def test_update_profiles_excludes_invalid_frequency_without_failing(frequency):
    valid_profile = {
        "frequency": 5,
        "varBinds": [["SNMPv2-MIB", "sysUpTime", 0]],
    }
    walk_profile = {
        "condition": {"type": "walk"},
        "varBinds": [["SNMPv2-MIB"]],
    }
    manager = ProfilesManager(Mock())
    manager.gather_elements = Mock(
        return_value={
            "invalid": {**valid_profile, "frequency": frequency},
            "valid": valid_profile,
            "walk": walk_profile,
        }
    )
    manager.update_collection = Mock()

    manager.update_all()

    manager.update_collection.assert_called_once_with(
        {"valid": valid_profile, "walk": walk_profile}
    )


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
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_FROM_MONGO",
        False,
    )
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
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_FROM_MONGO",
        False,
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
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_FROM_MONGO",
        False,
    )
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
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_FROM_MONGO",
        False,
    )
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
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_FROM_MONGO",
        False,
    )
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
