from unittest import TestCase
from unittest.mock import patch, Mock

from splunk_connect_for_snmp.common.schema_migration import fetch_schema_version, save_schema_version, migrate_database, \
    migrate_to_version_1


class TestSchemaMigration(TestCase):
    @patch("pymongo.collection.Collection.find_one")
    def test_fetch_schema_version(self, m_find_one):
        m_find_one.return_value = {"version": 2}
        result = fetch_schema_version()
        self.assertEqual(2, result)

    @patch("pymongo.collection.Collection.find_one")
    def test_fetch_schema_version_missing(self, m_find_one):
        m_find_one.return_value = None
        result = fetch_schema_version()
        self.assertEqual(0, result)

    @patch("pymongo.collection.Collection.update_one")
    def test_save_schema_version(self, m_update_one):
        save_schema_version(7)
        calls = m_update_one.call_args_list

        self.assertEqual(1, len(calls))
        self.assertEqual(({}, {'$set': {'version': 7}}), calls[0].args)

    @patch("splunk_connect_for_snmp.common.schema_migration.fetch_schema_version")
    @patch("splunk_connect_for_snmp.common.schema_migration.save_schema_version")
    @patch("splunk_connect_for_snmp.common.schema_migration.migrate_to_version_1")
    def test_migrate_database(self, m_version_1, m_save, m_fetch):
        m_fetch.return_value = 0

        migrate_database()

        calls = m_save.call_args_list
        self.assertEqual(1, len(calls))
        self.assertEqual(1, calls[0].args[0])

        m_version_1.assert_called()

    @patch('splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager')
    @patch("pymongo.collection.Collection.update")
    def test_migrate_to_version_1(self, m_update, m_task_manager):
        periodic_obj_mock = Mock()
        m_task_manager.return_value = periodic_obj_mock
        migrate_to_version_1()

        calls = m_update.call_args_list

        self.assertEqual(1, len(calls))
        self.assertEqual(({}, {'$unset': {'attributes': 1}}, False, True), calls[0].args)

        periodic_obj_mock.delete_all_poll_tasks.assert_called()
        periodic_obj_mock.rerun_all_walks.assert_called()


