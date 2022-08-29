from unittest import TestCase
from unittest.mock import MagicMock, patch

from pysnmp.smi.error import SmiError


@patch("pymongo.MongoClient")
@patch("mongolock.MongoLock.__init__")
@patch("mongolock.MongoLock.lock")
@patch("mongolock.MongoLock.release")
class TestTasks(TestCase):
    @patch("splunk_connect_for_snmp.snmp.tasks.get_inventory")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.__init__")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.do_work")
    @patch("time.time")
    def test_walk(
        self,
        m_time,
        m_do_work,
        m_poller,
        m_get_inventory,
        m_release,
        m_lock,
        m_mongo_lock,
        m_mongo_client,
    ):
        from splunk_connect_for_snmp.snmp.tasks import walk

        m_mongo_client.return_value = MagicMock()
        m_mongo_lock.return_value = None
        m_time.return_value = 1640692955.365186

        m_poller.return_value = None

        kwargs = {"address": "192.168.0.1"}
        m_do_work.return_value = (False, {"test": "value1"})

        result = walk(**kwargs)

        m_lock.assert_called()
        m_lock.m_release()

        self.assertEqual(
            {
                "time": 1640692955.365186,
                "address": "192.168.0.1",
                "result": {"test": "value1"},
            },
            result,
        )

    @patch("splunk_connect_for_snmp.snmp.tasks.get_inventory")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.__init__")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.do_work")
    @patch("time.time")
    def test_poll(
        self,
        m_time,
        m_do_work,
        m_poller,
        m_get_inventory,
        m_release,
        m_lock,
        m_mongo_lock,
        m_mongo_client,
    ):
        from splunk_connect_for_snmp.snmp.tasks import poll

        m_mongo_client.return_value = MagicMock()
        m_mongo_lock.return_value = None
        m_time.return_value = 1640692955.365186

        m_poller.return_value = None

        kwargs = {"address": "192.168.0.1", "profiles": ["profile1"], "frequency": 70}
        m_do_work.return_value = (False, {"test": "value1"})

        result = poll(**kwargs)

        m_lock.assert_called()
        m_lock.m_release()

        self.assertEqual(
            {
                "time": 1640692955.365186,
                "address": "192.168.0.1",
                "result": {"test": "value1"},
                "frequency": 70,
                "detectchange": False,
            },
            result,
        )

    @patch("splunk_connect_for_snmp.snmp.tasks.get_inventory")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.__init__")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.do_work")
    @patch("time.time")
    def test_poll_with_group(
        self,
        m_time,
        m_do_work,
        m_poller,
        m_get_inventory,
        m_release,
        m_lock,
        m_mongo_lock,
        m_mongo_client,
    ):
        from splunk_connect_for_snmp.snmp.tasks import poll

        m_mongo_client.return_value = MagicMock()
        m_mongo_lock.return_value = None
        m_time.return_value = 1640692955.365186

        m_poller.return_value = None

        kwargs = {
            "address": "192.168.0.1",
            "profiles": ["profile1"],
            "frequency": 70,
            "group": "group1",
        }
        m_do_work.return_value = (False, {"test": "value1"})

        result = poll(**kwargs)

        m_lock.assert_called()
        m_lock.m_release()

        self.assertEqual(
            {
                "time": 1640692955.365186,
                "address": "192.168.0.1",
                "result": {"test": "value1"},
                "frequency": 70,
                "group": "group1",
                "detectchange": False,
            },
            result,
        )

    @patch("splunk_connect_for_snmp.snmp.tasks.get_inventory")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.__init__")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.do_work")
    @patch("time.time")
    def test_walk_with_group(
        self,
        m_time,
        m_do_work,
        m_poller,
        m_get_inventory,
        m_release,
        m_lock,
        m_mongo_lock,
        m_mongo_client,
    ):
        from splunk_connect_for_snmp.snmp.tasks import walk

        m_mongo_client.return_value = MagicMock()
        m_mongo_lock.return_value = None
        m_time.return_value = 1640692955.365186

        m_poller.return_value = None

        kwargs = {"address": "192.168.0.1", "group": "group1"}
        m_do_work.return_value = (False, {"test": "value1"})

        result = walk(**kwargs)

        m_lock.assert_called()
        m_lock.m_release()

        self.assertEqual(
            {
                "time": 1640692955.365186,
                "address": "192.168.0.1",
                "group": "group1",
                "result": {"test": "value1"},
            },
            result,
        )

    @patch("pysnmp.smi.rfc1902.ObjectType.resolveWithMib")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.process_snmp_data")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.__init__")
    @patch("time.time")
    def test_trap(
        self,
        m_time,
        m_poller,
        m_process_data,
        m_resolved,
        m_release,
        m_lock,
        m_mongo_lock,
        m_mongo_client,
    ):
        from splunk_connect_for_snmp.snmp.tasks import trap

        m_time.return_value = 1640692955.365186

        m_resolved.return_value = None

        work = {"data": [("asd", "tre")], "host": "192.168.0.1"}
        m_process_data.return_value = (False, [], {"test": "value1"})
        m_poller.builder = MagicMock()
        m_poller.return_value = None
        m_poller.trap = trap
        m_poller.trap.mib_view_controller = MagicMock()
        result = trap(work)

        self.assertEqual(
            {
                "address": "192.168.0.1",
                "detectchange": False,
                "result": {"test": "value1"},
                "sourcetype": "sc4snmp:traps",
                "time": 1640692955.365186,
            },
            result,
        )

    @patch("pysnmp.smi.rfc1902.ObjectType.resolveWithMib")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.process_snmp_data")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.is_mib_known")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.load_mibs")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.__init__")
    @patch("time.time")
    def test_trap_retry_translation(
        self,
        m_time,
        m_poller,
        m_load_mib,
        m_is_mib_known,
        m_process_data,
        m_resolved,
        *mongo_args
    ):
        from splunk_connect_for_snmp.snmp.tasks import trap

        m_time.return_value = 1640692955.365186

        m_resolved.side_effect = [SmiError, "TEST1"]
        m_is_mib_known.return_value = (True, "SOME-MIB")
        m_poller.return_value = None
        work = {"data": [("asd", "tre")], "host": "192.168.0.1"}
        m_process_data.return_value = (False, [], {"test": "value1"})
        m_poller.trap = trap
        m_poller.trap.mib_view_controller = MagicMock()
        m_poller.trap.already_loaded_mibs = set()
        result = trap(work)

        calls = m_load_mib.call_args_list
        self.assertEqual({"SOME-MIB"}, calls[0][0][0])

        process_calls = m_process_data.call_args_list
        self.assertEqual(["TEST1"], process_calls[0][0][0])

        self.assertEqual(
            {
                "address": "192.168.0.1",
                "detectchange": False,
                "result": {"test": "value1"},
                "sourcetype": "sc4snmp:traps",
                "time": 1640692955.365186,
            },
            result,
        )

    @patch("pysnmp.smi.rfc1902.ObjectType.resolveWithMib")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.process_snmp_data")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.is_mib_known")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.load_mibs")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.__init__")
    @patch("time.time")
    def test_trap_retry_translation_failed(
        self,
        m_time,
        m_poller,
        m_load_mib,
        m_is_mib_known,
        m_process_data,
        m_resolved,
        m_release,
        m_lock,
        m_mongo_lock,
        m_mongo_client,
    ):
        from splunk_connect_for_snmp.snmp.tasks import trap

        m_time.return_value = 1640692955.365186

        m_resolved.side_effect = [SmiError, SmiError]
        m_is_mib_known.return_value = (True, "SOME-MIB")

        work = {"data": [("asd", "tre")], "host": "192.168.0.1"}
        m_process_data.return_value = (False, [], {"test": "value1"})
        m_poller.return_value = None
        m_poller.trap = trap
        m_poller.trap.mib_view_controller = MagicMock()
        m_poller.trap.already_loaded_mibs = set()
        result = trap(work)

        calls = m_load_mib.call_args_list

        process_calls = m_process_data.call_args_list
        self.assertEqual([], process_calls[0][0][0])

        self.assertEqual({"SOME-MIB"}, calls[0][0][0])
        self.assertEqual(
            {
                "address": "192.168.0.1",
                "detectchange": False,
                "result": {"test": "value1"},
                "sourcetype": "sc4snmp:traps",
                "time": 1640692955.365186,
            },
            result,
        )
