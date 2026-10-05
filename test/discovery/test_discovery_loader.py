from unittest import TestCase
from unittest.mock import mock_open, patch

from splunk_connect_for_snmp.customtaskmanager import DISCOVERY_TASK
from splunk_connect_for_snmp.discovery import loader


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
