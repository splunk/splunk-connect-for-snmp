from unittest import TestCase, mock
from unittest.mock import patch, mock_open, Mock


from splunk_connect_for_snmp.common.inventory_record import InventoryRecord
from splunk_connect_for_snmp.inventory.loader import gen_walk_task, load, transform_address_to_key
from pymongo.results import UpdateResult

mock_inventory = """address,port,version,community,secret,securityEngine,walk_interval,profiles,SmartProfiles,delete
192.168.0.1,,2c,public,,,1805,test_1,False,False"""

mock_inventory_with_comment = """address,port,version,community,secret,securityEngine,walk_interval,profiles,SmartProfiles,delete
#192.168.0.1,,2c,public,,,1805,test_1,False,False"""

mock_inventory_delete = """address,port,version,community,secret,securityEngine,walk_interval,profiles,SmartProfiles,delete
192.168.0.1,,2c,public,,,1805,test_1,False,True"""

expected_managed_task = {"some": 1, "test": 2, "data": 3}


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

        inventory_record = InventoryRecord.from_dict(inventory_record_json)
        result = gen_walk_task(inventory_record)

        self.assertEqual("sc4snmp;192.68.0.1:456;walk", result["name"])
        self.assertEqual("splunk_connect_for_snmp.snmp.tasks.walk", result["task"])
        self.assertEqual("192.68.0.1:456", result["target"])
        self.assertEqual([], result["args"])
        self.assertEqual({'address': '192.68.0.1:456'}, result["kwargs"])
        self.assertEqual("_chain", type(result["options"]["link"]).__name__)
        self.assertEqual("splunk_connect_for_snmp.enrich.tasks.enrich", result["options"]["link"].tasks[0].name)
        self.assertEqual("splunk_connect_for_snmp.inventory.tasks.inventory_setup_poller",
                         result["options"]["link"].tasks[1].tasks[0].name)
        self.assertEqual("splunk_connect_for_snmp.splunk.tasks.prepare",
                         result["options"]["link"].tasks[1].tasks[1].tasks[0].name)
        self.assertEqual("splunk_connect_for_snmp.splunk.tasks.send",
                         result["options"]["link"].tasks[1].tasks[1].tasks[1].name)
        self.assertEqual({'every': 3456, 'period': 'seconds'}, result["interval"])
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

        inventory_record = InventoryRecord.from_dict(inventory_record_json)
        result = gen_walk_task(inventory_record)

        self.assertEqual("sc4snmp;192.68.0.1;walk", result["name"])
        self.assertEqual("splunk_connect_for_snmp.snmp.tasks.walk", result["task"])
        self.assertEqual("192.68.0.1", result["target"])
        self.assertEqual([], result["args"])
        self.assertEqual({'address': '192.68.0.1'}, result["kwargs"])
        self.assertEqual("_chain", type(result["options"]["link"]).__name__)
        self.assertEqual("splunk_connect_for_snmp.enrich.tasks.enrich", result["options"]["link"].tasks[0].name)
        self.assertEqual("splunk_connect_for_snmp.inventory.tasks.inventory_setup_poller",
                         result["options"]["link"].tasks[1].tasks[0].name)
        self.assertEqual("splunk_connect_for_snmp.splunk.tasks.prepare",
                         result["options"]["link"].tasks[1].tasks[1].tasks[0].name)
        self.assertEqual("splunk_connect_for_snmp.splunk.tasks.send",
                         result["options"]["link"].tasks[1].tasks[1].tasks[1].name)
        self.assertEqual({'every': 3456, 'period': 'seconds'}, result["interval"])
        self.assertTrue(result["enabled"])
        self.assertTrue(result["run_immediately"])

    @mock.patch("splunk_connect_for_snmp.inventory.loader.gen_walk_task")
    @patch('builtins.open', new_callable=mock_open, read_data=mock_inventory)
    @patch('splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager')
    @mock.patch("pymongo.collection.Collection.update_one")
    @patch("splunk_connect_for_snmp.inventory.loader.migrate_database")
    def test_load_new_record(self, m_migrate, m_mongo_collection, m_taskManager, m_open, walk_task):
        walk_task.return_value = expected_managed_task
        m_mongo_collection.return_value = UpdateResult({"n": 0, "nModified": 1, "upserted": 1}, True)
        periodic_obj_mock = Mock()
        m_taskManager.return_value = periodic_obj_mock
        self.assertEqual(False, load())

        periodic_obj_mock.manage_task.assert_called_with(**expected_managed_task)

    @mock.patch("splunk_connect_for_snmp.inventory.loader.gen_walk_task")
    @patch('builtins.open', new_callable=mock_open, read_data=mock_inventory)
    @patch('splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager')
    @mock.patch("pymongo.collection.Collection.update_one")
    @patch("splunk_connect_for_snmp.inventory.loader.migrate_database")
    def test_load_modified_record(self, m_migrate, m_mongo_collection, m_taskManager, m_open, walk_task):
        walk_task.return_value = expected_managed_task
        m_mongo_collection.return_value = UpdateResult({"n": 1, "nModified": 1, "upserted": None}, True)
        periodic_obj_mock = Mock()
        m_taskManager.return_value = periodic_obj_mock
        self.assertEqual(False, load())

        periodic_obj_mock.manage_task.assert_called_with(**expected_managed_task)

    @patch('builtins.open', new_callable=mock_open, read_data=mock_inventory)
    @patch('splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager')
    @mock.patch("pymongo.collection.Collection.update_one")
    @patch("splunk_connect_for_snmp.inventory.loader.migrate_database")
    def test_load_unchanged_record(self, m_migrate, m_mongo_collection, m_taskManager, m_open):
        m_mongo_collection.return_value = UpdateResult({"n": 1, "nModified": 0, "upserted": None}, True)
        periodic_obj_mock = Mock()
        m_taskManager.return_value = periodic_obj_mock
        self.assertEqual(False, load())

        periodic_obj_mock.manage_task.assert_not_called()

    @patch('builtins.open', new_callable=mock_open, read_data=mock_inventory_with_comment)
    @patch('splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager')
    @mock.patch("pymongo.collection.Collection.update_one")
    @patch("splunk_connect_for_snmp.inventory.loader.migrate_database")
    def test_ignoring_comment(self, m_migrate, m_mongo_collection, m_taskManager, m_open):
        periodic_obj_mock = Mock()
        m_taskManager.return_value = periodic_obj_mock
        self.assertEqual(False, load())

        m_mongo_collection.assert_not_called()
        periodic_obj_mock.manage_task.assert_not_called()

    @patch('builtins.open', new_callable=mock_open, read_data=mock_inventory_delete)
    @patch('splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager')
    @mock.patch("pymongo.collection.Collection.delete_one")
    @mock.patch("pymongo.collection.Collection.remove")
    @patch("splunk_connect_for_snmp.inventory.loader.migrate_database")
    def test_deleting_record(self, m_migrate, m_remove, m_delete, m_taskManager, m_open):
        periodic_obj_mock = Mock()
        m_taskManager.return_value = periodic_obj_mock
        self.assertEqual(False, load())

        periodic_obj_mock.disable_tasks.assert_called_with("192.168.0.1")
        m_delete.assert_called_with({"address": "192.168.0.1", "port": 161})
        m_remove.assert_called_with({"address": "192.168.0.1"})

    @mock.patch("splunk_connect_for_snmp.inventory.loader.gen_walk_task")
    @patch('builtins.open', new_callable=mock_open, read_data=mock_inventory)
    @mock.patch("pymongo.collection.Collection.update_one")
    @mock.patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager.manage_task")
    @patch("splunk_connect_for_snmp.inventory.loader.migrate_database")
    def test_inventory_errors(self, m_migrate, m_manage_task, m_mongo_collection, m_open, walk_task):
        walk_task.return_value = expected_managed_task
        m_mongo_collection.return_value = UpdateResult({"n": 0, "nModified": 1, "upserted": 1}, True)
        m_manage_task.side_effect = Exception('Boom!')

        self.assertEqual(True, load())

    def test_transform_address_to_key_161(self):
        self.assertEqual(transform_address_to_key("127.0.0.1", 161), "127.0.0.1")
        self.assertEqual(transform_address_to_key("127.0.0.1", "161"), "127.0.0.1")

    def test_transform_address_to_key(self):
        self.assertEqual(transform_address_to_key("127.0.0.1", 32), "127.0.0.1:32")
        self.assertEqual(transform_address_to_key("127.0.0.1", "162"), "127.0.0.1:162")
        self.assertEqual(transform_address_to_key("127.0.0.1", 1), "127.0.0.1:1")
