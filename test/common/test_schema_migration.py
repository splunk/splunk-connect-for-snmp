from unittest import TestCase
from unittest.mock import ANY, MagicMock, Mock, patch, mock_open, call

from celery import chain, group, signature
from celery.schedules import schedule
from pymongo import ASCENDING

from splunk_connect_for_snmp.common.schema_migration import (
    fetch_schema_version,
    migrate_database,
    migrate_to_version_1,
    migrate_to_version_2,
    migrate_to_version_3,
    migrate_to_version_4,
    migrate_to_version_6,
    save_schema_version,
    transform_mongodb_periodic_to_redbeat,
)
from splunk_connect_for_snmp.common.task_generator import WalkTaskGenerator

files_contents = ["""address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete
group1,,2c,public,,,1805,group_profile,False,False
0.0.0.0,162,3,,my_secret,112233445566aabbcc,18,solo_profile1;solo_profile2,True,False""",
    """
    groups:
      switches:
        - address: 18.223.238.221
          port: 1161
          community: 'public'
    profiles:
      single_profile_1:
        frequency: 6
        varBinds:
          - [ "IF-MIB","ifInDiscards",1 ]
          - [ "IF-MIB","ifOutErrors" ]
          - [ "SNMPv2-MIB", "sysDescr",0 ]
          """
]


class TestSchemaMigration(TestCase):
    def test_fetch_schema_version(self):
        mc = MagicMock()
        mc.sc4snmp.schema_version.find_one.return_value = {"version": 2}
        result = fetch_schema_version(mc)
        self.assertEqual(2, result)

    def test_fetch_schema_version_missing(self):
        mc = MagicMock()
        mc.sc4snmp.schema_version.find_one.return_value = None
        result = fetch_schema_version(mc)
        self.assertEqual(0, result)

    def test_save_schema_version(self):
        mc = MagicMock()
        save_schema_version(mc, 7)
        calls = mc.sc4snmp.schema_version.update_one.call_args_list

        self.assertEqual(1, len(calls))
        self.assertEqual(({}, {"$set": {"version": 7}}), calls[0].args)

    @patch("splunk_connect_for_snmp.common.schema_migration.fetch_schema_version")
    @patch("splunk_connect_for_snmp.common.schema_migration.save_schema_version")
    @patch("splunk_connect_for_snmp.common.schema_migration.migrate_to_version_2")
    @patch("splunk_connect_for_snmp.common.schema_migration.migrate_to_version_1")
    @patch("splunk_connect_for_snmp.common.schema_migration.CURRENT_SCHEMA_VERSION", 3)
    def test_migrate_database(self, m_version_1, m_version_2, m_save, m_fetch):
        mc = MagicMock()
        m_fetch.return_value = 0

        migrate_database(mc, MagicMock())

        calls = m_save.call_args_list
        self.assertEqual(1, len(calls))
        self.assertEqual(3, calls[0].args[1])

        m_version_1.assert_called()
        m_version_2.assert_called()

    def test_migrate_to_version_1(self):
        periodic_obj_mock = Mock()
        mc = MagicMock()
        migrate_to_version_1(mc, periodic_obj_mock)

        calls = mc.sc4snmp.targets.update.call_args_list

        self.assertEqual(1, len(calls))
        self.assertEqual(
            ({}, {"$unset": {"attributes": 1}}, False, True), calls[0].args
        )

        periodic_obj_mock.delete_all_poll_tasks.assert_called()
        periodic_obj_mock.rerun_all_walks.assert_called()

    def test_migrate_to_version_2(self):
        periodic_obj_mock = Mock()
        mc = MagicMock()
        migrate_to_version_2(mc, periodic_obj_mock)

        periodic_obj_mock.delete_all_poll_tasks.assert_called()
        periodic_obj_mock.rerun_all_walks.assert_called()
        mc.sc4snmp.attributes.drop.assert_called()

    def test_migrate_to_version_3(self):
        periodic_obj_mock = Mock()
        mc = MagicMock()
        migrate_to_version_3(mc, periodic_obj_mock)

        mc.sc4snmp.attributes.create_index.assert_called_with(
            [("address", ASCENDING), ("group_key_hash", ASCENDING)]
        )

    @patch(
        "splunk_connect_for_snmp.common.schema_migration.transform_mongodb_periodic_to_redbeat"
    )
    def test_migrate_to_version_4(self, transform_mongodb_periodic_to_redbeat):
        periodic_obj_mock = Mock()
        mc = MagicMock()
        migrate_to_version_4(mc, periodic_obj_mock)
        mc.sc4snmp.schedules.drop.assert_called()

    def test_transform_mongodb_periodic_to_redbeat(self):
        old_schedules = [
            {
                "name": f"sc4snmp;127.0.0.1;walk",
                "task": "splunk_connect_for_snmp.snmp.tasks.walk",
                "target": "127.0.0.1",
                "args": [],
                "kwargs": {
                    "address": "127.0.0.1",
                    "profile": "walk1",
                },
                "options": {
                    "link": chain(
                        signature("splunk_connect_for_snmp.enrich.tasks.enrich"),
                        group(
                            signature(
                                "splunk_connect_for_snmp.inventory.tasks.inventory_setup_poller"
                            ),
                            chain(
                                signature(
                                    "splunk_connect_for_snmp.splunk.tasks.prepare"
                                ),
                                signature("splunk_connect_for_snmp.splunk.tasks.send"),
                            ),
                        ),
                    ),
                },
                "interval": {"every": 30, "period": "seconds"},
                "enabled": True,
                "total_run_count": 0,
                "run_immediately": True,
            }
        ]
        new_schedule = {
            "name": f"sc4snmp;127.0.0.1;walk",
            "task": "splunk_connect_for_snmp.snmp.tasks.walk",
            "target": "127.0.0.1",
            "args": [],
            "kwargs": {
                "address": "127.0.0.1",
                "profile": "walk1",
            },
            "options": WalkTaskGenerator.WALK_CHAIN_OF_TASKS,
            "schedule": schedule(30),
            "enabled": True,
            "run_immediately": True,
            "app": ANY,
        }
        mc = MagicMock()
        mc.find.return_value = old_schedules
        periodic_obj_mock = Mock()
        transform_mongodb_periodic_to_redbeat(mc, periodic_obj_mock)
        periodic_obj_mock.manage_task.assert_called_with(**new_schedule)

    def test_transform_mongodb_periodic_to_redbeat_more_than_one_walk(self):
        old_schedules = [
            {
                "name": f"sc4snmp;127.0.0.1;walk",
                "task": "splunk_connect_for_snmp.snmp.tasks.walk",
                "target": "127.0.0.1",
                "args": [],
                "kwargs": {
                    "address": "127.0.0.1",
                    "profile": "walk1",
                },
                "options": {
                    "link": chain(
                        signature("splunk_connect_for_snmp.enrich.tasks.enrich"),
                        group(
                            signature(
                                "splunk_connect_for_snmp.inventory.tasks.inventory_setup_poller"
                            ),
                            chain(
                                signature(
                                    "splunk_connect_for_snmp.splunk.tasks.prepare"
                                ),
                                signature("splunk_connect_for_snmp.splunk.tasks.send"),
                            ),
                        ),
                    ),
                },
                "interval": {"every": 30, "period": "seconds"},
                "enabled": True,
                "total_run_count": 0,
                "run_immediately": True,
            },
            {
                "name": f"sc4snmp;127.0.0.2;walk",
                "task": "splunk_connect_for_snmp.snmp.tasks.walk",
                "target": "127.0.0.2",
                "args": [],
                "kwargs": {
                    "address": "127.0.0.2",
                    "profile": None,
                },
                "options": {
                    "link": chain(
                        signature("splunk_connect_for_snmp.enrich.tasks.enrich"),
                        group(
                            signature(
                                "splunk_connect_for_snmp.inventory.tasks.inventory_setup_poller"
                            ),
                            chain(
                                signature(
                                    "splunk_connect_for_snmp.splunk.tasks.prepare"
                                ),
                                signature("splunk_connect_for_snmp.splunk.tasks.send"),
                            ),
                        ),
                    ),
                },
                "interval": {"every": 400, "period": "seconds"},
                "enabled": True,
                "total_run_count": 0,
                "run_immediately": True,
            },
        ]
        new_schedule = [
            {
                "name": f"sc4snmp;127.0.0.1;walk",
                "task": "splunk_connect_for_snmp.snmp.tasks.walk",
                "target": "127.0.0.1",
                "args": [],
                "kwargs": {
                    "address": "127.0.0.1",
                    "profile": "walk1",
                },
                "options": WalkTaskGenerator.WALK_CHAIN_OF_TASKS,
                "schedule": schedule(30),
                "enabled": True,
                "run_immediately": True,
                "app": ANY,
            },
            {
                "name": f"sc4snmp;127.0.0.2;walk",
                "task": "splunk_connect_for_snmp.snmp.tasks.walk",
                "target": "127.0.0.2",
                "args": [],
                "kwargs": {
                    "address": "127.0.0.2",
                    "profile": None,
                },
                "options": WalkTaskGenerator.WALK_CHAIN_OF_TASKS,
                "schedule": schedule(400),
                "enabled": True,
                "run_immediately": True,
                "app": ANY,
            },
        ]
        mc = MagicMock()
        mc.find.return_value = old_schedules
        periodic_obj_mock = Mock()
        transform_mongodb_periodic_to_redbeat(mc, periodic_obj_mock)
        calls = periodic_obj_mock.manage_task.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].kwargs, new_schedule[0])
        self.assertEqual(calls[1].kwargs, new_schedule[1])

    @patch(
        "builtins.open", new_callable=mock_open, read_data=files_contents[0]
    )
    def test_migrate_to_version_6(self, m_inventory):
        m_inventory.side_effect = [mock_open(read_data=content).return_value for content in files_contents]
        periodic_obj_mock = Mock()
        mongo_client = MagicMock()

        calls_inventory = [
            call({
                "address": "group1",
                "port": 161,
                "version": "2c",
                "community": "public",
                "secret": "",
                "security_engine": "",
                "walk_interval": 1805,
                "profiles": "group_profile",
                "smart_profiles": False,
                "delete": False
            }),
            call({
                "address": "0.0.0.0",
                "port": 162,
                "version": "3",
                "community": "",
                "secret": "my_secret",
                "security_engine": "112233445566aabbcc",
                "walk_interval": 1800,
                "profiles": "solo_profile1;solo_profile2",
                "smart_profiles": True,
                "delete": False
            })
        ]

        call_group = [{
            "switches": [
                {"address": "18.223.238.221", "port": 1161, "community": "public"}
            ]
        }]

        call_profiles = [{
            "single_profile_1": {
                "frequency": 6,
                "varBinds": [["IF-MIB", "ifInDiscards", 1], ["IF-MIB", "ifOutErrors"], ["SNMPv2-MIB", "sysDescr", 0]]
            }
        }]

        migrate_to_version_6(mongo_client, periodic_obj_mock)
        mongo_client.sc4snmp.inventory_ui.insert.assert_has_calls(calls_inventory)
        self.assertEqual(mongo_client.sc4snmp.groups_ui.insert_many.call_args, call(call_group))
        self.assertEqual(mongo_client.sc4snmp.profiles_ui.insert_many.call_args, call(call_profiles))

