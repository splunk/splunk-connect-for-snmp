from unittest import TestCase, mock
from unittest.mock import Mock, mock_open, patch
import os

from celery.schedules import schedule
from pymongo.results import UpdateResult

from splunk_connect_for_snmp.common.inventory_record import InventoryRecord
from splunk_connect_for_snmp.inventory.loader import (
    gen_walk_task,
    load,
    transform_address_to_key,
)

mock_inventory = """address,port,version,community,secret,securityEngine,walk_interval,profiles,SmartProfiles,delete
192.168.0.1,,2c,public,,,1805,test_1,False,False"""

mock_inventory_with_comment = """address,port,version,community,secret,securityEngine,walk_interval,profiles,SmartProfiles,delete
#192.168.0.1,,2c,public,,,1805,test_1,False,False"""

mock_inventory_delete = """address,port,version,community,secret,securityEngine,walk_interval,profiles,SmartProfiles,delete
192.168.0.1,,2c,public,,,1805,test_1,False,True"""

mock_inventory_delete_non_default = """address,port,version,community,secret,securityEngine,walk_interval,profiles,SmartProfiles,delete
192.168.0.1,345,2c,public,,,1805,test_1,False,True"""

mock_inventory_small_walk = """address,port,version,community,secret,securityEngine,walk_interval,profiles,SmartProfiles,delete
192.168.0.1,,2c,public,,,1805,test_1;walk1;walk2,False,False"""

mock_inventory_group = """address,port,version,community,secret,securityEngine,walk_interval,profiles,SmartProfiles,delete
testing,,2c,public,,,1805,test_1,False,False"""

mock_inventory_group_delete = """address,port,version,community,secret,securityEngine,walk_interval,profiles,SmartProfiles,delete
testing,,2c,public,,,1805,test_1,False,True"""

testing_group = """groups:
    testing:
      - 127.0.0.1
      - 192.168.0.1:1161"""

expected_managed_task = {"some": 1, "test": 2, "data": 3}

default_profiles = {
    "test1": {
        "type": "walk",
        "varBinds": [
            ["IF-MIB", "ifInDiscards", 1],
            ["IF-MIB", "ifOutErrors"],
            ["SNMPv2-MIB", "sysDescr", 0],
        ],
    }
}


class TestLoader(TestCase):
    def test_walk_task(self):
        inventory_record_json = {
            "address": "192.68.0.1",
            "port": 456,
            "version": "3",
            "community": "public",
            "secret": "some_secret",
            "securityEngine": "test_123",
            "walk_interval": 3456,
            "profiles": "profile1;profile2;profile3",
            "SmartProfiles": True,
            "delete": False,
        }

        inventory_record = InventoryRecord(**inventory_record_json)
        result = gen_walk_task(inventory_record)

        self.assertEqual("sc4snmp;192.68.0.1:456;walk", result["name"])
        self.assertEqual("splunk_connect_for_snmp.snmp.tasks.walk", result["task"])
        self.assertEqual("192.68.0.1:456", result["target"])
        self.assertEqual([], result["args"])
        self.assertEqual(
            {"address": "192.68.0.1:456", "profile": None}, result["kwargs"]
        )
        self.assertEqual("_chain", type(result["options"]["link"]).__name__)
        self.assertEqual(
            "splunk_connect_for_snmp.enrich.tasks.enrich",
            result["options"]["link"].tasks[0].name,
        )
        self.assertEqual(
            "splunk_connect_for_snmp.inventory.tasks.inventory_setup_poller",
            result["options"]["link"].tasks[1].tasks[0].name,
        )
        self.assertEqual(
            "splunk_connect_for_snmp.splunk.tasks.prepare",
            result["options"]["link"].tasks[1].tasks[1].tasks[0].name,
        )
        self.assertEqual(
            "splunk_connect_for_snmp.splunk.tasks.send",
            result["options"]["link"].tasks[1].tasks[1].tasks[1].name,
        )
        self.assertEqual(schedule(3456), result["schedule"])
        self.assertTrue(result["enabled"])
        self.assertTrue(result["run_immediately"])

    def test_walk_task_for_port_161(self):
        inventory_record_json = {
            "address": "192.68.0.1",
            "port": 161,
            "version": "3",
            "community": "public",
            "secret": "some_secret",
            "securityEngine": "test_123",
            "walk_interval": 3456,
            "profiles": "profile1;profile2;profile3",
            "SmartProfiles": True,
            "delete": False,
        }

        inventory_record = InventoryRecord(**inventory_record_json)
        result = gen_walk_task(inventory_record)

        self.assertEqual("sc4snmp;192.68.0.1;walk", result["name"])
        self.assertEqual("splunk_connect_for_snmp.snmp.tasks.walk", result["task"])
        self.assertEqual("192.68.0.1", result["target"])
        self.assertEqual([], result["args"])
        self.assertEqual({"address": "192.68.0.1", "profile": None}, result["kwargs"])
        self.assertEqual("_chain", type(result["options"]["link"]).__name__)
        self.assertEqual(
            "splunk_connect_for_snmp.enrich.tasks.enrich",
            result["options"]["link"].tasks[0].name,
        )
        self.assertEqual(
            "splunk_connect_for_snmp.inventory.tasks.inventory_setup_poller",
            result["options"]["link"].tasks[1].tasks[0].name,
        )
        self.assertEqual(
            "splunk_connect_for_snmp.splunk.tasks.prepare",
            result["options"]["link"].tasks[1].tasks[1].tasks[0].name,
        )
        self.assertEqual(
            "splunk_connect_for_snmp.splunk.tasks.send",
            result["options"]["link"].tasks[1].tasks[1].tasks[1].name,
        )
        self.assertEqual(schedule(3456), result["schedule"])
        self.assertTrue(result["enabled"])
        self.assertTrue(result["run_immediately"])

    @patch("builtins.open", new_callable=mock_open, read_data=mock_inventory_small_walk)
    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    @mock.patch("pymongo.collection.Collection.update_one")
    @patch("splunk_connect_for_snmp.inventory.loader.migrate_database")
    @mock.patch(
        "splunk_connect_for_snmp.common.profiles.ProfilesManager.update_all_profiles"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.profiles.ProfilesManager.return_all_profiles"
    )
    def test_load_new_record_small_walk(
        self,
        m_load_profiles,
        m_gather_profiles,
        m_migrate,
        m_mongo_collection,
        m_taskManager,
        m_open,
    ):
        profiles = {
            "walk1": {
                "condition": {"type": "walk"},
                "varBinds": [
                    ["IF-MIB", "ifInDiscards", 1],
                    ["IF-MIB", "ifOutErrors"],
                    ["SNMPv2-MIB", "sysDescr", 0],
                ],
            },
            "walk2": {
                "condition": {"type": "walk"},
                "varBinds": [
                    ["IF-MIB", "ifInDiscards", 1],
                    ["IF-MIB", "ifOutErrors"],
                    ["SNMPv2-MIB", "sysDescr", 0],
                ],
            },
        }

        m_mongo_collection.return_value = UpdateResult(
            {"n": 0, "nModified": 1, "upserted": 1}, True
        )
        periodic_obj_mock = Mock()
        m_taskManager.return_value = periodic_obj_mock
        m_load_profiles.return_value = profiles
        self.assertEqual(False, load())
        self.assertEqual(
            {"address": "192.168.0.1", "profile": "walk2"},
            periodic_obj_mock.manage_task.call_args.kwargs["kwargs"],
        )

    @mock.patch("splunk_connect_for_snmp.inventory.loader.gen_walk_task")
    @patch("builtins.open", new_callable=mock_open, read_data=mock_inventory)
    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    @mock.patch("pymongo.collection.Collection.update_one")
    @patch("splunk_connect_for_snmp.inventory.loader.migrate_database")
    @mock.patch(
        "splunk_connect_for_snmp.common.profiles.ProfilesManager.update_all_profiles"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.profiles.ProfilesManager.return_all_profiles"
    )
    def test_load_new_record(
        self,
        m_load_profiles,
        m_update_profiles,
        m_migrate,
        m_mongo_collection,
        m_taskManager,
        m_open,
        walk_task,
    ):
        walk_task.return_value = expected_managed_task
        m_mongo_collection.return_value = UpdateResult(
            {"n": 0, "nModified": 1, "upserted": 1}, True
        )
        periodic_obj_mock = Mock()
        m_taskManager.return_value = periodic_obj_mock
        m_load_profiles.return_value = default_profiles
        self.assertEqual(False, load())

        periodic_obj_mock.manage_task.assert_called_with(**expected_managed_task)

    @mock.patch("splunk_connect_for_snmp.inventory.loader.gen_walk_task")
    @patch("builtins.open", new_callable=mock_open, read_data=mock_inventory)
    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    @mock.patch("pymongo.collection.Collection.update_one")
    @patch("splunk_connect_for_snmp.inventory.loader.migrate_database")
    @mock.patch(
        "splunk_connect_for_snmp.common.profiles.ProfilesManager.update_all_profiles"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.profiles.ProfilesManager.return_all_profiles"
    )
    def test_load_modified_record(
        self,
        m_load_profiles,
        m_update_profiles,
        m_migrate,
        m_mongo_collection,
        m_taskManager,
        m_open,
        walk_task,
    ):
        walk_task.return_value = expected_managed_task
        m_mongo_collection.return_value = UpdateResult(
            {"n": 1, "nModified": 1, "upserted": None}, True
        )
        periodic_obj_mock = Mock()
        m_taskManager.return_value = periodic_obj_mock
        m_load_profiles.return_value = default_profiles
        self.assertEqual(False, load())

        periodic_obj_mock.manage_task.assert_called_with(**expected_managed_task)

    @patch("builtins.open", new_callable=mock_open, read_data=mock_inventory)
    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    @mock.patch("pymongo.collection.Collection.update_one")
    @patch("splunk_connect_for_snmp.inventory.loader.migrate_database")
    @mock.patch(
        "splunk_connect_for_snmp.common.profiles.ProfilesManager.update_all_profiles"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.profiles.ProfilesManager.return_all_profiles"
    )
    def test_load_unchanged_record(
        self,
        m_load_profiles,
        m_update_profiles,
        m_migrate,
        m_mongo_collection,
        m_taskManager,
        m_open,
    ):
        m_mongo_collection.return_value = UpdateResult(
            {"n": 1, "nModified": 0, "upserted": None}, True
        )
        periodic_obj_mock = Mock()
        m_taskManager.return_value = periodic_obj_mock
        m_load_profiles.return_value = default_profiles
        self.assertEqual(False, load())

        periodic_obj_mock.manage_task.assert_not_called()

    @patch(
        "builtins.open", new_callable=mock_open, read_data=mock_inventory_with_comment
    )
    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    @mock.patch("pymongo.collection.Collection.update_one")
    @patch("splunk_connect_for_snmp.inventory.loader.migrate_database")
    @mock.patch(
        "splunk_connect_for_snmp.common.profiles.ProfilesManager.update_all_profiles"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.profiles.ProfilesManager.return_all_profiles"
    )
    def test_ignoring_comment(
        self,
        m_load_profiles,
        m_update_profiles,
        m_migrate,
        m_mongo_collection,
        m_taskManager,
        m_open,
    ):
        periodic_obj_mock = Mock()
        m_taskManager.return_value = periodic_obj_mock
        m_load_profiles.return_value = default_profiles
        self.assertEqual(False, load())

        m_mongo_collection.assert_not_called()
        periodic_obj_mock.manage_task.assert_not_called()

    @patch("builtins.open", new_callable=mock_open, read_data=mock_inventory_delete)
    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    @mock.patch("pymongo.collection.Collection.delete_one")
    @mock.patch("pymongo.collection.Collection.remove")
    @patch("splunk_connect_for_snmp.inventory.loader.migrate_database")
    @mock.patch(
        "splunk_connect_for_snmp.common.profiles.ProfilesManager.update_all_profiles"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.profiles.ProfilesManager.return_all_profiles"
    )
    def test_deleting_record(
        self,
        m_load_profiles,
        m_update_profiles,
        m_migrate,
        m_remove,
        m_delete,
        m_taskManager,
        m_open,
    ):
        periodic_obj_mock = Mock()
        m_taskManager.return_value = periodic_obj_mock
        m_load_profiles.return_value = default_profiles
        self.assertEqual(False, load())

        periodic_obj_mock.delete_all_tasks_of_host.assert_called_with("192.168.0.1")
        m_delete.assert_called_with({"address": "192.168.0.1", "port": 161})

        calls = m_remove.call_args_list

        self.assertEqual(2, len(calls))
        self.assertEqual(({"address": "192.168.0.1"},), calls[0].args)
        self.assertEqual(({"address": "192.168.0.1"},), calls[1].args)

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data=mock_inventory_delete_non_default,
    )
    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    @mock.patch("pymongo.collection.Collection.delete_one")
    @mock.patch("pymongo.collection.Collection.remove")
    @patch("splunk_connect_for_snmp.inventory.loader.migrate_database")
    @mock.patch(
        "splunk_connect_for_snmp.common.profiles.ProfilesManager.update_all_profiles"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.profiles.ProfilesManager.return_all_profiles"
    )
    def test_deleting_record_non_default_port(
        self,
        m_load_profiles,
        m_update_profiles,
        m_migrate,
        m_remove,
        m_delete,
        m_taskManager,
        m_open,
    ):
        periodic_obj_mock = Mock()
        m_taskManager.return_value = periodic_obj_mock
        m_load_profiles.return_value = default_profiles
        self.assertEqual(False, load())

        periodic_obj_mock.delete_all_tasks_of_host.assert_called_with("192.168.0.1:345")
        m_delete.assert_called_with({"address": "192.168.0.1", "port": 345})

        calls = m_remove.call_args_list

        self.assertEqual(2, len(calls))
        self.assertEqual(({"address": "192.168.0.1:345"},), calls[0].args)
        self.assertEqual(({"address": "192.168.0.1:345"},), calls[1].args)

    @patch("splunk_connect_for_snmp.inventory.loader.gen_walk_task")
    @patch("builtins.open", new_callable=mock_open, read_data=mock_inventory)
    @patch("pymongo.collection.Collection.update_one")
    @patch(
        "splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager.manage_task"
    )
    @patch("splunk_connect_for_snmp.inventory.loader.migrate_database")
    @mock.patch(
        "splunk_connect_for_snmp.common.profiles.ProfilesManager.update_all_profiles"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.profiles.ProfilesManager.return_all_profiles"
    )
    def test_inventory_errors(
        self,
        m_load_profiles,
        m_update_profiles,
        m_migrate,
        m_manage_task,
        m_mongo_collection,
        m_open,
        walk_task,
    ):
        walk_task.return_value = expected_managed_task
        m_mongo_collection.return_value = UpdateResult(
            {"n": 0, "nModified": 1, "upserted": 1}, True
        )
        m_manage_task.side_effect = Exception("Boom!")
        m_load_profiles.return_value = default_profiles

        self.assertEqual(True, load())

    @mock.patch("splunk_connect_for_snmp.inventory.loader.gen_walk_task")
    @patch("builtins.open", new_callable=mock_open)
    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    @mock.patch("pymongo.collection.Collection.update_one")
    @patch("splunk_connect_for_snmp.inventory.loader.migrate_database")
    @mock.patch(
        "splunk_connect_for_snmp.common.profiles.ProfilesManager.update_all_profiles"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.profiles.ProfilesManager.return_all_profiles"
    )
    def test_load_new_records_from_group(
        self,
        m_load_profiles,
        m_update_profiles,
        m_migrate,
        m_mongo_collection,
        m_taskManager,
        m_open,
        walk_task,
    ):
        mock_files = [mock_open(read_data=content).return_value for content in [mock_inventory_group, testing_group]]
        m_open.side_effect = mock_files
        walk_task.return_value = expected_managed_task
        m_mongo_collection.return_value = UpdateResult(
            {"n": 0, "nModified": 2, "upserted": 2}, True
        )
        periodic_obj_mock = Mock()
        m_taskManager.return_value = periodic_obj_mock
        m_load_profiles.return_value = default_profiles
        self.assertEqual(False, load())

        periodic_obj_mock.manage_task.assert_called_with(**expected_managed_task)


    @patch("builtins.open", new_callable=mock_open)
    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    @mock.patch("pymongo.collection.Collection.delete_one")
    @mock.patch("pymongo.collection.Collection.remove")
    @patch("splunk_connect_for_snmp.inventory.loader.migrate_database")
    @mock.patch(
        "splunk_connect_for_snmp.common.profiles.ProfilesManager.update_all_profiles"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.profiles.ProfilesManager.return_all_profiles"
    )
    def test_deleting_records_from_group(
        self,
        m_load_profiles,
        m_update_profiles,
        m_migrate,
        m_remove,
        m_delete,
        m_taskManager,
        m_open,
    ):
        mock_files = [mock_open(read_data=content).return_value for content in [mock_inventory_group_delete, testing_group]]
        m_open.side_effect = mock_files
        periodic_obj_mock = Mock()
        m_taskManager.return_value = periodic_obj_mock
        m_load_profiles.return_value = default_profiles
        self.assertEqual(False, load())

        periodic_obj_mock.delete_all_tasks_of_host.assert_any_call("127.0.0.1")
        m_delete.assert_any_call({"address": "127.0.0.1", "port": 161})
        periodic_obj_mock.delete_all_tasks_of_host.assert_any_call("192.168.0.1:1161")
        m_delete.assert_any_call({"address": "192.168.0.1", "port": 1161})

        calls = m_remove.call_args_list

        self.assertEqual(4, len(calls))
        self.assertEqual(({"address": "127.0.0.1"},), calls[0].args)
        self.assertEqual(({"address": "127.0.0.1"},), calls[1].args)
        self.assertEqual(({"address": "192.168.0.1:1161"},), calls[2].args)
        self.assertEqual(({"address": "192.168.0.1:1161"},), calls[3].args)

    def test_transform_address_to_key_161(self):
        self.assertEqual(transform_address_to_key("127.0.0.1", 161), "127.0.0.1")
        self.assertEqual(transform_address_to_key("127.0.0.1", "161"), "127.0.0.1")

    def test_transform_address_to_key(self):
        self.assertEqual(transform_address_to_key("127.0.0.1", 32), "127.0.0.1:32")
        self.assertEqual(transform_address_to_key("127.0.0.1", "162"), "127.0.0.1:162")
        self.assertEqual(transform_address_to_key("127.0.0.1", 1), "127.0.0.1:1")
