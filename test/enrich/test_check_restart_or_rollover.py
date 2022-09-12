from unittest import TestCase
from unittest.mock import Mock, patch

from splunk_connect_for_snmp.enrich.tasks import check_restart_or_rollover


class TestEnrich(TestCase):
    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    def test_check_restart_or_rollover_no_engine_sysuptime_far_from_limit(
        self, m_task_manager
    ):
        periodic_obj_mock = Mock()
        m_task_manager.return_value = periodic_obj_mock
        current_target = {"sysUpTime": {"value": 23000}}
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

        check_restart_or_rollover(
            current_target, result, targets_collection, "192.168.0.1", 20
        )
        expected_args = {"name": "sc4snmp;192.168.0.1;walk", "run_immediately": True}
        periodic_obj_mock.manage_task.assert_called_with(**expected_args)
        calls = targets_collection.update_one.call_args_list

        self.assertEqual({"address": "192.168.0.1"}, calls[0][0][0])
        self.assertEqual(
            {
                "$set": {
                    "sysUpTime": {"value": 30, "type": "m", "oid": "1.2.3.4.5"},
                    "sysUpTimeRollover": 0,
                }
            },
            calls[0][0][1],
        )

    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    def test_check_restart_or_rollover_no_engine_sysuptime_close_to_limit(
        self, m_task_manager
    ):
        periodic_obj_mock = Mock()
        m_task_manager.return_value = periodic_obj_mock
        current_target = {"sysUpTime": {"value": 4294967285}}
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

        check_restart_or_rollover(
            current_target, result, targets_collection, "192.168.0.1", 20
        )
        periodic_obj_mock.manage_task.assert_not_called()

        calls = targets_collection.update_one.call_args_list

        self.assertEqual({"address": "192.168.0.1"}, calls[0][0][0])
        self.assertEqual(
            {
                "$set": {
                    "sysUpTime": {"value": 50, "type": "m", "oid": "1.2.3.4.5"},
                    "sysUpTimeRollover": 1,
                }
            },
            calls[0][0][1],
        )

    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    def test_check_restart_or_rollover_no_engine_sysuptime_increase(
        self, m_task_manager
    ):
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

        check_restart_or_rollover(
            current_target, result, targets_collection, "192.168.0.1", 20
        )
        periodic_obj_mock.manage_task.assert_not_called()

        calls = targets_collection.update_one.call_args_list

        self.assertEqual({"address": "192.168.0.1"}, calls[0][0][0])
        self.assertEqual(
            {
                "$set": {
                    "sysUpTime": {"value": 50, "type": "m", "oid": "1.2.3.4.5"},
                    "sysUpTimeRollover": 0,
                }
            },
            calls[0][0][1],
        )

    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    def test_check_restart_or_rollover_sysuptime_close_to_limit_engine_decrease(
        self, m_task_manager
    ):
        periodic_obj_mock = Mock()
        m_task_manager.return_value = periodic_obj_mock
        current_target = {
            "sysUpTime": {"value": 4294967285},
            "snmpEngineTime": {"value": 500},
        }
        result = {
            "SOME_KEY": {
                "metrics": {
                    "SNMPv2-MIB.sysUpTime": {
                        "value": 30,
                        "type": "m",
                        "oid": "1.2.3.4.5",
                    }
                }
            },
            "SOME_KEY_2": {
                "fields": {
                    "SNMP-FRAMEWORK-MIB.snmpEngineTime": {
                        "value": 10,
                        "type": "f",
                        "oid": "1.2.3.4.5.6",
                    }
                }
            },
        }
        targets_collection = Mock()

        check_restart_or_rollover(
            current_target, result, targets_collection, "192.168.0.1", 20
        )
        expected_args = {"name": "sc4snmp;192.168.0.1;walk", "run_immediately": True}
        periodic_obj_mock.manage_task.assert_called_with(**expected_args)
        calls = targets_collection.update_one.call_args_list

        self.assertEqual({"address": "192.168.0.1"}, calls[0][0][0])
        self.assertEqual(
            {
                "$set": {
                    "sysUpTime": {"value": 30, "type": "m", "oid": "1.2.3.4.5"},
                    "snmpEngineTime": {"value": 10, "type": "f", "oid": "1.2.3.4.5.6"},
                    "sysUpTimeRollover": 0,
                }
            },
            calls[0][0][1],
        )

    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    def test_check_restart_or_rollover_sysuptime_far_from_limit_engine_increase(
        self, m_task_manager
    ):
        periodic_obj_mock = Mock()
        m_task_manager.return_value = periodic_obj_mock
        current_target = {
            "sysUpTime": {"value": 4064967195},
            "snmpEngineTime": {"value": 500},
        }
        result = {
            "SOME_KEY": {
                "metrics": {
                    "SNMPv2-MIB.sysUpTime": {
                        "value": 30,
                        "type": "m",
                        "oid": "1.2.3.4.5",
                    }
                }
            },
            "SOME_KEY_2": {
                "fields": {
                    "SNMP-FRAMEWORK-MIB.snmpEngineTime": {
                        "value": 1000,
                        "type": "f",
                        "oid": "1.2.3.4.5.6",
                    }
                }
            },
        }
        targets_collection = Mock()

        check_restart_or_rollover(
            current_target, result, targets_collection, "192.168.0.1", 20
        )
        expected_args = {"name": "sc4snmp;192.168.0.1;walk", "run_immediately": True}
        periodic_obj_mock.manage_task.assert_called_with(**expected_args)
        calls = targets_collection.update_one.call_args_list

        self.assertEqual({"address": "192.168.0.1"}, calls[0][0][0])
        self.assertEqual(
            {
                "$set": {
                    "sysUpTime": {"value": 30, "type": "m", "oid": "1.2.3.4.5"},
                    "snmpEngineTime": {
                        "value": 1000,
                        "type": "f",
                        "oid": "1.2.3.4.5.6",
                    },
                    "sysUpTimeRollover": 0,
                }
            },
            calls[0][0][1],
        )

    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    def test_check_restart_or_rollover_sysuptime_far_from_limit_engine_decrease(
        self, m_task_manager
    ):
        periodic_obj_mock = Mock()
        m_task_manager.return_value = periodic_obj_mock
        current_target = {
            "sysUpTime": {"value": 4064967195},
            "snmpEngineTime": {"value": 500},
        }
        result = {
            "SOME_KEY": {
                "metrics": {
                    "SNMPv2-MIB.sysUpTime": {
                        "value": 30,
                        "type": "m",
                        "oid": "1.2.3.4.5",
                    }
                }
            },
            "SOME_KEY_2": {
                "fields": {
                    "SNMP-FRAMEWORK-MIB.snmpEngineTime": {
                        "value": 10,
                        "type": "f",
                        "oid": "1.2.3.4.5.6",
                    }
                }
            },
        }
        targets_collection = Mock()

        check_restart_or_rollover(
            current_target, result, targets_collection, "192.168.0.1", 20
        )
        expected_args = {"name": "sc4snmp;192.168.0.1;walk", "run_immediately": True}
        periodic_obj_mock.manage_task.assert_called_with(**expected_args)
        calls = targets_collection.update_one.call_args_list

        self.assertEqual({"address": "192.168.0.1"}, calls[0][0][0])
        self.assertEqual(
            {
                "$set": {
                    "sysUpTime": {"value": 30, "type": "m", "oid": "1.2.3.4.5"},
                    "snmpEngineTime": {"value": 10, "type": "f", "oid": "1.2.3.4.5.6"},
                    "sysUpTimeRollover": 0,
                }
            },
            calls[0][0][1],
        )

    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    def test_check_restart_or_rollover_sysuptime_close_to_limit_engine_increase(
        self, m_task_manager
    ):
        periodic_obj_mock = Mock()
        m_task_manager.return_value = periodic_obj_mock
        current_target = {
            "sysUpTime": {"value": 4294967285},
            "snmpEngineTime": {"value": 500},
        }
        result = {
            "SOME_KEY": {
                "metrics": {
                    "SNMPv2-MIB.sysUpTime": {
                        "value": 30,
                        "type": "m",
                        "oid": "1.2.3.4.5",
                    }
                }
            },
            "SOME_KEY_2": {
                "fields": {
                    "SNMP-FRAMEWORK-MIB.snmpEngineTime": {
                        "value": 1000,
                        "type": "f",
                        "oid": "1.2.3.4.5.6",
                    }
                }
            },
        }
        targets_collection = Mock()

        check_restart_or_rollover(
            current_target, result, targets_collection, "192.168.0.1", 20
        )
        periodic_obj_mock.manage_task.assert_not_called()

        calls = targets_collection.update_one.call_args_list

        self.assertEqual({"address": "192.168.0.1"}, calls[0][0][0])
        self.assertEqual(
            {
                "$set": {
                    "sysUpTime": {"value": 30, "type": "m", "oid": "1.2.3.4.5"},
                    "snmpEngineTime": {
                        "value": 1000,
                        "type": "f",
                        "oid": "1.2.3.4.5.6",
                    },
                    "sysUpTimeRollover": 1,
                }
            },
            calls[0][0][1],
        )

    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    def test_check_restart_or_rollover_sysuptime_increase_engine_increase(
        self, m_task_manager
    ):
        periodic_obj_mock = Mock()
        m_task_manager.return_value = periodic_obj_mock
        current_target = {"sysUpTime": {"value": 40}, "snmpEngineTime": {"value": 500}}
        result = {
            "SOME_KEY": {
                "metrics": {
                    "SNMPv2-MIB.sysUpTime": {
                        "value": 50,
                        "type": "m",
                        "oid": "1.2.3.4.5",
                    }
                }
            },
            "SOME_KEY_2": {
                "fields": {
                    "SNMP-FRAMEWORK-MIB.snmpEngineTime": {
                        "value": 1000,
                        "type": "f",
                        "oid": "1.2.3.4.5.6",
                    }
                }
            },
        }
        targets_collection = Mock()

        check_restart_or_rollover(
            current_target, result, targets_collection, "192.168.0.1", 20
        )
        periodic_obj_mock.manage_task.assert_not_called()

        calls = targets_collection.update_one.call_args_list

        self.assertEqual({"address": "192.168.0.1"}, calls[0][0][0])
        self.assertEqual(
            {
                "$set": {
                    "sysUpTime": {"value": 50, "type": "m", "oid": "1.2.3.4.5"},
                    "snmpEngineTime": {
                        "value": 1000,
                        "type": "f",
                        "oid": "1.2.3.4.5.6",
                    },
                    "sysUpTimeRollover": 0,
                }
            },
            calls[0][0][1],
        )
