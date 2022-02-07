from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch

from splunk_connect_for_snmp.common.schema_migration import (
    fetch_schema_version,
    migrate_database,
    migrate_to_version_1,
    save_schema_version,
)


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
    def test_migrate_database(self, m_version_1, m_version_2, m_save, m_fetch):
        mc = MagicMock()
        m_fetch.return_value = 0

        migrate_database(mc, MagicMock())

        calls = m_save.call_args_list
        self.assertEqual(1, len(calls))
        self.assertEqual(2, calls[0].args[1])

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
