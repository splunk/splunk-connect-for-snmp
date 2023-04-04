from unittest import TestCase, mock
from unittest.mock import Mock, patch

from celery.schedules import schedule

from splunk_connect_for_snmp.common.inventory_record import InventoryRecord


class TestInventorySetupPoller(TestCase):
    @patch(
        "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.return_collection"
    )
    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    @mock.patch("pymongo.collection.Collection.find_one")
    @mock.patch("splunk_connect_for_snmp.inventory.tasks.assign_profiles")
    @mock.patch("splunk_connect_for_snmp.inventory.tasks.get_inventory")
    def test_inventory_setup_poller(
        self,
        m_get_inventory,
        m_assign_profiles,
        m_find_one,
        m_task_manager,
        m_load_profiles,
    ):
        from splunk_connect_for_snmp.inventory.tasks import inventory_setup_poller

        periodic_obj_mock = Mock()
        m_load_profiles.return_value = []
        m_task_manager.return_value = periodic_obj_mock
        m_get_inventory.return_value = InventoryRecord(
            **{
                "address": "192.168.0.1",
                "port": "34",
                "version": "2c",
                "community": "public",
                "secret": "secret",
                "securityEngine": "ENGINE",
                "walk_interval": 1850,
                "profiles": "",
                "SmartProfiles": True,
                "delete": False,
            }
        )

        m_find_one.return_value = {
            "state": {
                "SNMPv2-MIB|sysDescr": {"value": "MIKROTIK"},
                "SNMPv2-MIB|sysName": {"value": "Linux Debian 2.0.1"},
                "SNMPv2-MIB|sysContact": {"value": "non-existing-name@splunk"},
            }
        }

        work = {"address": "192.168.0.1"}

        m_assign_profiles.return_value = {
            60: ["BaseUpTime"],
            30: ["profile5", "profile2"],
            20: ["profile1"],
        }, []

        # when
        inventory_setup_poller(work)

        calls = periodic_obj_mock.manage_task.call_args_list

        calls[0][1]["kwargs"]["profiles"] = set(calls[0][1]["kwargs"]["profiles"])
        calls[1][1]["kwargs"]["profiles"] = set(calls[1][1]["kwargs"]["profiles"])
        calls[2][1]["kwargs"]["profiles"] = set(calls[2][1]["kwargs"]["profiles"])
        self.assertEqual(
            {
                "address": "192.168.0.1",
                "profiles": {"BaseUpTime"},
                "priority": 2,
                "frequency": 60,
            },
            calls[0][1]["kwargs"],
        )
        self.assertEqual(
            {
                "address": "192.168.0.1",
                "priority": 2,
                "profiles": {"profile2", "profile5"},
                "frequency": 30,
            },
            calls[1][1]["kwargs"],
        )
        self.assertEqual(
            {
                "address": "192.168.0.1",
                "profiles": {"profile1"},
                "priority": 2,
                "frequency": 20,
            },
            calls[2][1]["kwargs"],
        )

        periodic_obj_mock.delete_unused_poll_tasks.assert_called_with(
            "192.168.0.1",
            [
                "sc4snmp;192.168.0.1;60;poll",
                "sc4snmp;192.168.0.1;30;poll",
                "sc4snmp;192.168.0.1;20;poll",
            ],
        )

    @patch(
        "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.return_collection"
    )
    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    @mock.patch("pymongo.collection.Collection.find_one")
    @mock.patch("pymongo.collection.Collection.replace_one")
    @mock.patch("splunk_connect_for_snmp.inventory.tasks.assign_profiles")
    @mock.patch("splunk_connect_for_snmp.inventory.tasks.get_inventory")
    @mock.patch("splunk_connect_for_snmp.inventory.tasks.generate_conditional_profile")
    def test_inventory_setup_poller_conditional_profile(
        self,
        generate_conditional_profile,
        m_get_inventory,
        m_assign_profiles,
        m_replace_one,
        m_find_one,
        m_task_manager,
        m_load_profiles,
    ):
        from splunk_connect_for_snmp.inventory.tasks import inventory_setup_poller

        periodic_obj_mock = Mock()
        m_load_profiles.return_value = []
        m_task_manager.return_value = periodic_obj_mock
        m_get_inventory.return_value = InventoryRecord(
            **{
                "address": "192.168.0.1",
                "port": "34",
                "version": "2c",
                "community": "public",
                "secret": "secret",
                "securityEngine": "ENGINE",
                "walk_interval": 1850,
                "profiles": "conditional_profile",
                "SmartProfiles": True,
                "delete": False,
            }
        )
        generate_conditional_profile.return_value = {
            "conditional_profile:192.168.0.1": {
                "frequency": 120,
                "varBinds": [["IF-MIB", "IfDescr", 1]],
            }
        }
        m_find_one.return_value = {
            "state": {
                "SNMPv2-MIB|sysDescr": {"value": "MIKROTIK"},
                "SNMPv2-MIB|sysName": {"value": "Linux Debian 2.0.1"},
                "SNMPv2-MIB|sysContact": {"value": "non-existing-name@splunk"},
            }
        }

        work = {"address": "192.168.0.1"}

        m_assign_profiles.return_value = {
            60: ["BaseUpTime"],
            30: ["profile5", "profile2"],
            20: ["profile1"],
        }, [
            {
                "conditional_profile": {
                    "frequency": 120,
                    "conditions": [
                        {
                            "operation": "equals",
                            "field": "IF-MIB.ifAdminStatus",
                            "value": "up",
                        }
                    ],
                    "varBinds": [["IF-MIB", "IfDescr"]],
                }
            }
        ]

        # when
        inventory_setup_poller(work)

        calls = periodic_obj_mock.manage_task.call_args_list

        calls[0][1]["kwargs"]["profiles"] = set(calls[0][1]["kwargs"]["profiles"])
        calls[1][1]["kwargs"]["profiles"] = set(calls[1][1]["kwargs"]["profiles"])
        calls[2][1]["kwargs"]["profiles"] = set(calls[2][1]["kwargs"]["profiles"])
        calls[3][1]["kwargs"]["profiles"] = set(calls[3][1]["kwargs"]["profiles"])
        self.assertEqual(
            {
                "address": "192.168.0.1",
                "profiles": {"BaseUpTime"},
                "priority": 2,
                "frequency": 60,
            },
            calls[0][1]["kwargs"],
        )
        self.assertEqual(
            {
                "address": "192.168.0.1",
                "priority": 2,
                "profiles": {"profile2", "profile5"},
                "frequency": 30,
            },
            calls[1][1]["kwargs"],
        )
        self.assertEqual(
            {
                "address": "192.168.0.1",
                "profiles": {"profile1"},
                "priority": 2,
                "frequency": 20,
            },
            calls[2][1]["kwargs"],
        )
        self.assertEqual(
            {
                "address": "192.168.0.1",
                "profiles": {"conditional_profile__192|168|0|1"},
                "priority": 2,
                "frequency": 120,
            },
            calls[3][1]["kwargs"],
        )
        periodic_obj_mock.delete_unused_poll_tasks.assert_called_with(
            "192.168.0.1",
            [
                "sc4snmp;192.168.0.1;60;poll",
                "sc4snmp;192.168.0.1;30;poll",
                "sc4snmp;192.168.0.1;20;poll",
                "sc4snmp;192.168.0.1;120;poll",
            ],
        )

    @patch(
        "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.return_collection"
    )
    def test_generate_poll_task_definition(self, rp):
        from splunk_connect_for_snmp.inventory.tasks import (
            generate_poll_task_definition,
        )

        active_schedules = []
        address = "192.168.0.1"
        assigned_profiles = {
            60: ["BaseUpTime"],
            30: ["profile5", "profile2"],
            20: ["profile1"],
        }
        period = 30
        result = generate_poll_task_definition(
            active_schedules, address, assigned_profiles, period
        )
        result["kwargs"]["profiles"] = set(result["kwargs"]["profiles"])
        self.assertEqual("sc4snmp;192.168.0.1;30;poll", result["name"])
        self.assertEqual("splunk_connect_for_snmp.snmp.tasks.poll", result["task"])
        self.assertEqual("192.168.0.1", result["target"])
        self.assertEqual([], result["args"])
        self.assertEqual(
            {
                "address": "192.168.0.1",
                "priority": 2,
                "profiles": {"profile2", "profile5"},
                "frequency": 30,
            },
            result["kwargs"],
        )
        self.assertEqual(
            "splunk_connect_for_snmp.enrich.tasks.enrich",
            result["options"]["link"].tasks[0].name,
        )
        self.assertEqual(
            "splunk_connect_for_snmp.splunk.tasks.prepare",
            result["options"]["link"].tasks[1].name,
        )
        self.assertEqual(
            "splunk_connect_for_snmp.splunk.tasks.send",
            result["options"]["link"].tasks[2].name,
        )
        self.assertEqual(schedule(30), result["schedule"])
        self.assertEqual(True, result["enabled"])
        self.assertEqual(False, result["run_immediately"])

        self.assertEqual("sc4snmp;192.168.0.1;30;poll", active_schedules[0])
