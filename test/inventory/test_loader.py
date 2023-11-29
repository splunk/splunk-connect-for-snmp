from unittest import TestCase, mock
from unittest.mock import Mock, mock_open, patch

from celery import chain, group, signature
from celery.schedules import schedule
from pymongo.results import UpdateResult

from splunk_connect_for_snmp.common.inventory_processor import gen_walk_task
from splunk_connect_for_snmp.common.inventory_record import InventoryRecord
from splunk_connect_for_snmp.inventory.loader import load, transform_address_to_key

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

chain_of_tasks_expiry_time = 120

mock_walk_chain_of_tasks = WALK_CHAIN_OF_TASKS = {
    "expires": chain_of_tasks_expiry_time,
    "link": chain(
        signature("splunk_connect_for_snmp.enrich.tasks.enrich")
        .set(queue="poll")
        .set(priority=4),
        group(
            signature(
                "splunk_connect_for_snmp.inventory.tasks.inventory_setup_poller",
            )
            .set(queue="poll")
            .set(priority=3),
            chain(
                signature("splunk_connect_for_snmp.splunk.tasks.prepare")
                .set(queue="send")
                .set(priority=1),
                signature("splunk_connect_for_snmp.splunk.tasks.send")
                .set(queue="send")
                .set(priority=0),
            ),
        ),
    ),
}

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


@mock.patch(
    "splunk_connect_for_snmp.common.task_generator.CHAIN_OF_TASKS_EXPIRY_TIME",
    chain_of_tasks_expiry_time,
)
@mock.patch(
    "splunk_connect_for_snmp.common.task_generator.WalkTaskGenerator.WALK_CHAIN_OF_TASKS",
    mock_walk_chain_of_tasks,
)
class TestLoader(TestCase):
    @mock.patch(
        "splunk_connect_for_snmp.common.inventory_processor.CONFIG_FROM_MONGO",
        False,
    )
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
            {
                "address": "192.68.0.1:456",
                "profile": None,
                "chain_of_tasks_expiry_time": 120,
            },
            result["kwargs"],
        )
        self.assertEqual("_chain", type(result["options"]["link"]).__name__)
        self.assertEqual(
            chain_of_tasks_expiry_time,
            result["options"]["expires"],
        )
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

    @mock.patch(
        "splunk_connect_for_snmp.common.inventory_processor.CONFIG_FROM_MONGO",
        False,
    )
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
        self.assertEqual(
            {
                "address": "192.68.0.1",
                "profile": None,
                "chain_of_tasks_expiry_time": chain_of_tasks_expiry_time,
            },
            result["kwargs"],
        )
        self.assertEqual("_chain", type(result["options"]["link"]).__name__)
        self.assertEqual(
            chain_of_tasks_expiry_time,
            result["options"]["expires"],
        )
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

    @mock.patch(
        "splunk_connect_for_snmp.common.inventory_processor.CONFIG_FROM_MONGO", False
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_FROM_MONGO", False
    )
    @mock.patch("splunk_connect_for_snmp.inventory.loader.CONFIG_FROM_MONGO", False)
    @patch("builtins.open", new_callable=mock_open, read_data=mock_inventory_small_walk)
    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    @mock.patch("pymongo.collection.Collection.update_one")
    @patch("splunk_connect_for_snmp.inventory.loader.migrate_database")
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.update_all"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.return_collection"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.GroupsManager.update_all"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.GroupsManager.return_collection"
    )
    @mock.patch("splunk_connect_for_snmp.inventory.loader.configure_ui_database")
    def test_load_new_record_small_walk(
        self,
        m_configure_ui_database,
        m_load_groups,
        m_update_groups,
        m_load_profiles,
        m_gather_elements,
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
            {
                "address": "192.168.0.1",
                "profile": "walk2",
                "chain_of_tasks_expiry_time": 120,
            },
            periodic_obj_mock.manage_task.call_args.kwargs["kwargs"],
        )

    @mock.patch(
        "splunk_connect_for_snmp.common.inventory_processor.CONFIG_FROM_MONGO", False
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_FROM_MONGO", False
    )
    @mock.patch("splunk_connect_for_snmp.inventory.loader.CONFIG_FROM_MONGO", False)
    @patch("splunk_connect_for_snmp.common.inventory_processor.gen_walk_task")
    @patch("builtins.open", new_callable=mock_open, read_data=mock_inventory)
    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    @mock.patch("pymongo.collection.Collection.update_one")
    @patch("splunk_connect_for_snmp.inventory.loader.migrate_database")
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.update_all"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.return_collection"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.GroupsManager.update_all"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.GroupsManager.return_collection"
    )
    @mock.patch("splunk_connect_for_snmp.inventory.loader.configure_ui_database")
    def test_load_new_record(
        self,
        m_configure_ui_database,
        m_load_groups,
        m_update_groups,
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

    @mock.patch(
        "splunk_connect_for_snmp.common.inventory_processor.CONFIG_FROM_MONGO", False
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_FROM_MONGO", False
    )
    @mock.patch("splunk_connect_for_snmp.inventory.loader.CONFIG_FROM_MONGO", False)
    @patch("splunk_connect_for_snmp.common.inventory_processor.gen_walk_task")
    @patch("builtins.open", new_callable=mock_open, read_data=mock_inventory)
    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    @mock.patch("pymongo.collection.Collection.update_one")
    @patch("splunk_connect_for_snmp.inventory.loader.migrate_database")
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.update_all"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.return_collection"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.GroupsManager.update_all"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.GroupsManager.return_collection"
    )
    @mock.patch("splunk_connect_for_snmp.inventory.loader.configure_ui_database")
    def test_load_modified_record(
        self,
        m_configure_ui_database,
        m_load_groups,
        m_update_groups,
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

    @mock.patch(
        "splunk_connect_for_snmp.common.inventory_processor.CONFIG_FROM_MONGO", False
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_FROM_MONGO", False
    )
    @mock.patch("splunk_connect_for_snmp.inventory.loader.CONFIG_FROM_MONGO", False)
    @mock.patch(
        "splunk_connect_for_snmp.inventory.loader.CHAIN_OF_TASKS_EXPIRY_TIME", 180
    )
    @patch("builtins.open", new_callable=mock_open, read_data=mock_inventory)
    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    @mock.patch("pymongo.collection.Collection.update_one")
    @patch("splunk_connect_for_snmp.inventory.loader.migrate_database")
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.update_all"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.return_collection"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.GroupsManager.update_all"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.GroupsManager.return_collection"
    )
    @mock.patch("splunk_connect_for_snmp.inventory.loader.configure_ui_database")
    def test_load_unchanged_record(
        self,
        m_configure_ui_database,
        m_load_groups,
        m_update_groups,
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
        periodic_obj_mock.did_expiry_time_change.return_value = False
        m_migrate.return_value = False
        m_load_profiles.return_value = default_profiles
        self.assertEqual(False, load())

        periodic_obj_mock.manage_task.assert_not_called()

    @mock.patch(
        "splunk_connect_for_snmp.common.inventory_processor.CONFIG_FROM_MONGO", False
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_FROM_MONGO", False
    )
    @mock.patch("splunk_connect_for_snmp.inventory.loader.CONFIG_FROM_MONGO", False)
    @mock.patch(
        "splunk_connect_for_snmp.inventory.loader.CHAIN_OF_TASKS_EXPIRY_TIME", 180
    )
    @patch("splunk_connect_for_snmp.common.inventory_processor.gen_walk_task")
    @patch("builtins.open", new_callable=mock_open, read_data=mock_inventory)
    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    @mock.patch("pymongo.collection.Collection.update_one")
    @patch("splunk_connect_for_snmp.inventory.loader.migrate_database")
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.update_all"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.return_collection"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.GroupsManager.update_all"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.GroupsManager.return_collection"
    )
    @mock.patch("splunk_connect_for_snmp.inventory.loader.configure_ui_database")
    def test_load_unchanged_record_with_new_expiry_time(
        self,
        m_configure_ui_database,
        m_load_groups,
        m_update_groups,
        m_load_profiles,
        m_update_profiles,
        m_migrate,
        m_mongo_collection,
        m_taskManager,
        m_open,
        m_gen_walk_task,
    ):
        m_mongo_collection.return_value = UpdateResult(
            {"n": 1, "nModified": 0, "upserted": None}, True
        )
        m_gen_walk_task.return_value = expected_managed_task
        periodic_obj_mock = Mock()
        m_taskManager.return_value = periodic_obj_mock
        periodic_obj_mock.did_expiry_time_change.return_value = True
        m_load_profiles.return_value = default_profiles
        self.assertEqual(False, load())

        periodic_obj_mock.manage_task.assert_called_with(**expected_managed_task)

    @mock.patch(
        "splunk_connect_for_snmp.common.inventory_processor.CONFIG_FROM_MONGO", False
    )
    @mock.patch(
        "splunk_connect_for_snmp.inventory.loader.CHAIN_OF_TASKS_EXPIRY_TIME", 180
    )
    @patch(
        "builtins.open", new_callable=mock_open, read_data=mock_inventory_with_comment
    )
    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    @mock.patch("pymongo.collection.Collection.update_one")
    @patch("splunk_connect_for_snmp.inventory.loader.migrate_database")
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.update_all"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.return_collection"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.GroupsManager.update_all"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.GroupsManager.return_collection"
    )
    @mock.patch("splunk_connect_for_snmp.inventory.loader.configure_ui_database")
    def test_ignoring_comment(
        self,
        m_configure_ui_database,
        m_load_groups,
        m_update_groups,
        m_load_profiles,
        m_update_profiles,
        m_migrate,
        m_mongo_collection,
        m_taskManager,
        m_open,
    ):

        periodic_obj_mock = Mock()
        m_taskManager.return_value = periodic_obj_mock
        m_taskManager.get_chain_of_task_expiry.return_value = 180
        m_load_profiles.return_value = default_profiles
        self.assertEqual(False, load())

        m_mongo_collection.assert_not_called()
        periodic_obj_mock.manage_task.assert_not_called()

    @mock.patch(
        "splunk_connect_for_snmp.common.inventory_processor.CONFIG_FROM_MONGO", False
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_FROM_MONGO", False
    )
    @mock.patch("splunk_connect_for_snmp.inventory.loader.CONFIG_FROM_MONGO", False)
    @patch("builtins.open", new_callable=mock_open, read_data=mock_inventory_delete)
    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    @mock.patch("pymongo.collection.Collection.delete_one")
    @mock.patch("pymongo.collection.Collection.delete_many")
    @patch("splunk_connect_for_snmp.inventory.loader.migrate_database")
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.update_all"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.return_collection"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.GroupsManager.update_all"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.GroupsManager.return_collection"
    )
    @mock.patch("splunk_connect_for_snmp.inventory.loader.configure_ui_database")
    def test_deleting_record(
        self,
        m_configure_ui_database,
        m_load_groups,
        m_update_groups,
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

    @mock.patch(
        "splunk_connect_for_snmp.common.inventory_processor.CONFIG_FROM_MONGO", False
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_FROM_MONGO", False
    )
    @mock.patch("splunk_connect_for_snmp.inventory.loader.CONFIG_FROM_MONGO", False)
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data=mock_inventory_delete_non_default,
    )
    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    @mock.patch("pymongo.collection.Collection.delete_one")
    @mock.patch("pymongo.collection.Collection.delete_many")
    @patch("splunk_connect_for_snmp.inventory.loader.migrate_database")
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.update_all"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.return_collection"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.GroupsManager.update_all"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.GroupsManager.return_collection"
    )
    @mock.patch("splunk_connect_for_snmp.inventory.loader.configure_ui_database")
    def test_deleting_record_non_default_port(
        self,
        m_configure_ui_database,
        m_load_groups,
        m_update_groups,
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

    @mock.patch(
        "splunk_connect_for_snmp.common.inventory_processor.CONFIG_FROM_MONGO", False
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.CONFIG_FROM_MONGO", False
    )
    @mock.patch("splunk_connect_for_snmp.inventory.loader.CONFIG_FROM_MONGO", False)
    @patch("splunk_connect_for_snmp.common.inventory_processor.gen_walk_task")
    @patch("builtins.open", new_callable=mock_open, read_data=mock_inventory)
    @patch("pymongo.collection.Collection.update_one")
    @patch(
        "splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager.manage_task"
    )
    @patch(
        "splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager.did_expiry_time_change"
    )
    @patch("splunk_connect_for_snmp.inventory.loader.migrate_database")
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.update_all"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.return_collection"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.GroupsManager.update_all"
    )
    @mock.patch(
        "splunk_connect_for_snmp.common.collection_manager.GroupsManager.return_collection"
    )
    @mock.patch("splunk_connect_for_snmp.inventory.loader.configure_ui_database")
    def test_inventory_errors(
        self,
        m_configure_ui_database,
        m_load_groups,
        m_update_groups,
        m_load_profiles,
        m_update_profiles,
        m_migrate,
        m_did_expire,
        m_manage_task,
        m_mongo_collection,
        m_open,
        walk_task,
    ):
        walk_task.return_value = expected_managed_task
        m_mongo_collection.return_value = UpdateResult(
            {"n": 0, "nModified": 1, "upserted": 1}, True
        )
        m_did_expire.return_value = True
        m_manage_task.side_effect = Exception("Boom!")
        m_load_profiles.return_value = default_profiles

        self.assertEqual(True, load())

    def test_transform_address_to_key_161(self):
        self.assertEqual(transform_address_to_key("127.0.0.1", 161), "127.0.0.1")
        self.assertEqual(transform_address_to_key("127.0.0.1", "161"), "127.0.0.1")

    def test_transform_address_to_key(self):
        self.assertEqual(transform_address_to_key("127.0.0.1", 32), "127.0.0.1:32")
        self.assertEqual(transform_address_to_key("127.0.0.1", "162"), "127.0.0.1:162")
        self.assertEqual(transform_address_to_key("127.0.0.1", 1), "127.0.0.1:1")
