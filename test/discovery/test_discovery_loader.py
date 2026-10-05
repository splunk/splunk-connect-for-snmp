from unittest import TestCase
from unittest.mock import mock_open, patch

from splunk_connect_for_snmp.customtaskmanager import DISCOVERY_TASK
from splunk_connect_for_snmp.discovery import loader

mock_discovery_config = """
ipv6Enabled: false
autodiscovery:
  subnet_v4:
    frequency: 86400
    delete_already_discovered: false
    network_address: 192.0.2.0/30
    version: "2c"
    community: "public"
    port: 161
  subnet_v6:
    frequency: 86400
    delete_already_discovered: false
    network_address: 2001:db8::/126
    version: "2c"
    community: "public"
    port: 161
"""


class TestDiscoveryLoader(TestCase):
    @patch("builtins.open", new_callable=mock_open, read_data="autodiscovery: {}\n")
    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    def test_expiry_check_is_scoped_to_discovery_tasks(self, m_task_manager, _):
        periodic_obj = m_task_manager.return_value
        periodic_obj.did_expiry_time_change.return_value = False

        self.assertEqual(0, loader.load())

        self.assertIsInstance(loader.CHAIN_OF_TASKS_EXPIRY_TIME, int)
        periodic_obj.did_expiry_time_change.assert_called_once_with(
            loader.CHAIN_OF_TASKS_EXPIRY_TIME, [DISCOVERY_TASK]
        )
        periodic_obj.delete_unused_discovery_tasks.assert_called_once_with([])

    @patch("builtins.open", new_callable=mock_open, read_data=mock_discovery_config)
    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    def test_unused_discovery_tasks_are_deleted(self, m_task_manager, _):
        periodic_obj = m_task_manager.return_value
        periodic_obj.did_expiry_time_change.return_value = False

        self.assertEqual(0, loader.load())

        periodic_obj.manage_task.assert_called_once()
        self.assertEqual(
            "sc4snmp;subnet_v4;discovery",
            periodic_obj.manage_task.call_args.kwargs["name"],
        )
        periodic_obj.delete_unused_discovery_tasks.assert_called_once_with(
            ["sc4snmp;subnet_v4;discovery"]
        )
