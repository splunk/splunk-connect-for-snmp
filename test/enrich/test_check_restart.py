from unittest import TestCase
from unittest.mock import Mock, patch

from splunk_connect_for_snmp.enrich.tasks import check_restart


class TestEnrich(TestCase):
    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    def test_check_restart(self, m_task_manager):
        periodic_obj_mock = Mock()
        m_task_manager.return_value = periodic_obj_mock
        current_target = {"sysUpTime": {"value": 40}}
        result = {
            "SOME_KEY": {
                "metrics": {
                    "SNMPv2-MIB.sysUpTime": {
                        "value": 30,
                        "type": "m",
                        "oid": "1.2.3.4.5",
                    }
                }
            }
        }
        targets_collection = Mock()

        check_restart(
            current_target, result, targets_collection, "192.168.0.1"
        )
        expected_args = {"name": "sc4snmp;192.168.0.1;walk", "run_immediately": True}
        periodic_obj_mock.manage_task.assert_called_with(**expected_args)
        calls = targets_collection.update_one.call_args_list

        self.assertEqual({"address": "192.168.0.1"}, calls[0][0][0])
        self.assertEqual(
            {"$set": {"sysUpTime": {"value": 30, "type": "m", "oid": "1.2.3.4.5"}}},
            calls[0][0][1],
        )

    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    def test_check_restart_not_applied(self, m_task_manager):
        periodic_obj_mock = Mock()
        m_task_manager.return_value = periodic_obj_mock
        current_target = {"sysUpTime": {"value": 40}}
        result = {
            "SOME_KEY": {
                "metrics": {
                    "SNMPv2-MIB.sysUpTime": {
                        "value": 50,
                        "type": "m",
                        "oid": "1.2.3.4.5",
                    }
                }
            }
        }
        targets_collection = Mock()

        check_restart(
            current_target, result, targets_collection, "192.168.0.1"
        )
        periodic_obj_mock.manage_task.assert_not_called()

        calls = targets_collection.update_one.call_args_list

        self.assertEqual({"address": "192.168.0.1"}, calls[0][0][0])
        self.assertEqual(
            {"$set": {"sysUpTime": {"value": 50, "type": "m", "oid": "1.2.3.4.5"}}},
            calls[0][0][1],
        )
