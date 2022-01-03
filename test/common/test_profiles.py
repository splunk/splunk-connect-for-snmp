from unittest import TestCase, mock
import os

from splunk_connect_for_snmp.common.profiles import load_profiles


def return_mocked_path(file_name):
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "base_profiles", file_name
    )


def return_yaml_profiles(args=None):
    return [return_mocked_path("base.yaml")]


def return_config(*args):
    return return_mocked_path("runtime_config.yaml")


def return_not_existing_file(*args):
    return return_mocked_path("runtime_config_that_doesnt_exist.yaml")


class TestProfiles(TestCase):

    @mock.patch('splunk_connect_for_snmp.common.profiles.os.listdir', return_not_existing_file)
    @mock.patch('splunk_connect_for_snmp.common.profiles.CONFIG_PATH', return_config())
    def test_config_file_not_found(self):
        self.assertEqual(load_profiles(), {})

    @mock.patch('splunk_connect_for_snmp.common.profiles.os.listdir', return_yaml_profiles)
    @mock.patch('splunk_connect_for_snmp.common.profiles.CONFIG_PATH', return_config())
    def test_read_base_profiles(self):
        active_profiles = {'BaseUpTime': {'frequency': 300, 'condition': {'type': 'base'}, 'varBinds': [['IF-MIB', 'ifName'], ['IF-MIB', 'ifAlias'], ['SNMPv2-MIB', 'sysUpTime', 0]]}, 'EnirchIF': {'frequency': 600, 'condition': {'type': 'base'}, 'varBinds': [['IF-MIB', 'ifDescr'], ['IF-MIB', 'ifAdminStatus'], ['IF-MIB', 'ifName'], ['IF-MIB', 'ifAlias']]}}
        self.assertEqual(load_profiles(), active_profiles)

    def test_runtime_profiles(self):
        pass

    def test_all_profiles(self):
        pass
