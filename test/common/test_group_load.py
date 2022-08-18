import os
from unittest import TestCase, mock
from unittest.mock import Mock

from splunk_connect_for_snmp.common.groups import get_group


def return_mocked_path(file_name):
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "mock_groups", file_name
    )


def return_not_existing_config(*args):
    return return_mocked_path("runtime_config_that_doesnt_exist.yaml")


def return_config(*args):
    return return_mocked_path("runtime_config_with_groups.yaml")


class TestGroups(TestCase):
    @mock.patch(
        "splunk_connect_for_snmp.common.groups.CONFIG_PATH",
        return_config(),
    )
    def test_get_group(self):
        addresses_1 = [
            {"ip": "127.0.0.1", "port": ""},
            {"ip": "0.0.0.0", "port": "1162"},
        ]
        returned_addresses_1 = get_group("routers")

        self.assertEqual(addresses_1, returned_addresses_1)

        addresses_2 = [
            {"ip": "23.10.152.23", "port": "1163"},
            {"ip": "255.4.24.4", "port": "1164"},
        ]
        returned_addresses_2 = get_group("switches")

        self.assertEqual(addresses_2, returned_addresses_2)

    @mock.patch(
        "splunk_connect_for_snmp.common.groups.CONFIG_PATH",
        return_not_existing_config(),
    )
    def test_config_file_not_found(self):
        with self.assertLogs(
            "splunk_connect_for_snmp.common.groups", level="INFO"
        ) as cm:
            result = get_group("switches")
            self.assertTrue(
                any(
                    [
                        el
                        for el in cm.output
                        if "runtime_config_that_doesnt_exist.yaml not found" in el
                    ]
                )
            )
