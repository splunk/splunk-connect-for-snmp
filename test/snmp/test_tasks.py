from unittest import TestCase
from unittest.mock import MagicMock, patch

from pysnmp.smi.error import NoSuchObjectError, SmiError


@patch("pymongo.MongoClient")
class TestTasks(TestCase):
    @patch("splunk_connect_for_snmp.snmp.manager.get_inventory")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.__init__")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.do_work")
    @patch("time.time")
    def test_walk(
        self,
        m_time,
        m_do_work,
        m_poller,
        m_get_inventory,
        m_mongo_client,
    ):
        m_poller.return_value = None
        from splunk_connect_for_snmp.snmp.tasks import poll

        m_mongo_client.return_value = MagicMock()
        m_time.return_value = 1640692955.365186

        kwargs = {"address": "192.168.0.1", "profiles": ["profile1"], "frequency": 70}
        m_do_work.return_value = (False, {"test": "value1"})

        result = poll(**kwargs)

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

    @patch("splunk_connect_for_snmp.snmp.manager.get_inventory")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.__init__")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.do_work")
    @patch("time.time")
    def test_poll_with_group(
        self,
        m_time,
        m_do_work,
        m_poller,
        m_get_inventory,
        m_mongo_client,
    ):
        m_poller.return_value = None
        from splunk_connect_for_snmp.snmp.tasks import poll

        m_time.return_value = 1640692955.365186

        kwargs = {
            "address": "192.168.0.1",
            "profiles": ["profile1"],
            "frequency": 70,
            "group": "group1",
        }
        m_do_work.return_value = (False, {"test": "value1"})

        result = poll(**kwargs)

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

    @patch("splunk_connect_for_snmp.snmp.manager.get_inventory")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.__init__")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.do_work")
    @patch("time.time")
    def test_walk_with_group(
        self,
        m_time,
        m_do_work,
        m_poller,
        m_get_inventory,
        m_mongo_client,
    ):
        m_poller.return_value = None
        from splunk_connect_for_snmp.snmp.tasks import walk

        m_mongo_client.return_value = MagicMock()
        m_time.return_value = 1640692955.365186

        kwargs = {
            "address": "192.168.0.1",
            "group": "group1",
            "chain_of_tasks_expiry_time": 120,
        }
        m_do_work.return_value = (False, {"test": "value1"})

        result = walk(**kwargs)

        self.assertEqual(
            {
                "time": 1640692955.365186,
                "address": "192.168.0.1",
                "group": "group1",
                "result": {"test": "value1"},
                "chain_of_tasks_expiry_time": 120,
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
        m_mongo_client,
    ):
        m_poller.return_value = None
        from splunk_connect_for_snmp.snmp.tasks import trap

        m_time.return_value = 1640692955.365186

        m_resolved.return_value = None

        work = {"data": [("asd", "tre")], "host": "192.168.0.1"}
        m_process_data.return_value = (False, [], {"test": "value1"})
        m_poller.builder = MagicMock()
        m_poller.trap = trap
        m_poller.trap.mib_view_controller = MagicMock()
        trap.already_loaded_mibs = set()
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
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.__init__")
    @patch("time.time")
    def test_trap_with_context_engine_id(
        self,
        m_time,
        m_poller,
        m_process_data,
        m_resolved,
        m_mongo_client,
    ):
        m_poller.return_value = None
        from splunk_connect_for_snmp.snmp.tasks import trap

        m_time.return_value = 1640692955.365186

        m_resolved.return_value = None

        work = {
            "data": [("asd", "tre")],
            "host": "192.168.0.1",
            "fields": {"context_engine_id": "80003a8c04"},
        }
        m_process_data.return_value = (False, [], {"test": "value1"})
        m_poller.builder = MagicMock()
        m_poller.trap = trap
        m_poller.trap.mib_view_controller = MagicMock()
        trap.already_loaded_mibs = set()
        result = trap(work)

        self.assertEqual(
            {
                "address": "192.168.0.1",
                "detectchange": False,
                "result": {"test": "value1"},
                "sourcetype": "sc4snmp:traps",
                "time": 1640692955.365186,
                "fields": {"context_engine_id": "80003a8c04"},
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
        m_mongo_client,
    ):
        m_poller.return_value = None
        from splunk_connect_for_snmp.snmp.tasks import trap

        m_time.return_value = 1640692955.365186

        m_resolved.side_effect = [SmiError, "TEST1"]
        m_is_mib_known.return_value = (True, "SOME-MIB")
        work = {"data": [("asd", "tre")], "host": "192.168.0.1"}
        m_process_data.return_value = (False, [], {"test": "value1"})
        m_poller.trap = trap
        m_poller.trap.mib_view_controller = MagicMock()
        m_poller.trap.mib_view_controller.get_node_location.side_effect = (
            NoSuchObjectError()
        )
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
        m_mongo_client,
    ):
        m_poller.return_value = None
        from splunk_connect_for_snmp.snmp.tasks import trap

        m_time.return_value = 1640692955.365186

        m_resolved.side_effect = [SmiError, SmiError]
        m_is_mib_known.return_value = (True, "SOME-MIB")

        work = {"data": [("asd", "tre")], "host": "192.168.0.1"}
        m_process_data.return_value = (False, [], {"test": "value1"})
        m_poller.trap = trap
        m_poller.trap.mib_view_controller = MagicMock()
        m_poller.trap.mib_view_controller.get_node_location.side_effect = (
            NoSuchObjectError()
        )
        m_poller.trap.already_loaded_mibs = set()
        result = trap(work)

        calls = m_load_mib.call_args_list

        process_calls = m_process_data.call_args_list
        self.assertEqual([], process_calls[0][0][0])

        self.assertEqual({"SOME-MIB"}, calls[0][0][0])
        self.assertEqual("192.168.0.1", result["address"])
        self.assertIn("sc4snmp::unresolved", result["result"])
        self.assertIn(
            "unresolved::asd",
            result["result"]["sc4snmp::unresolved"]["fields"],
        )

    @patch("pysnmp.smi.rfc1902.ObjectType.resolveWithMib")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.process_snmp_data")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.is_mib_known")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.load_mibs")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.__init__")
    @patch("time.time")
    def test_trap_keeps_varbind_when_mib_unknown(
        self,
        m_time,
        m_poller,
        m_load_mib,
        m_is_mib_known,
        m_process_data,
        m_resolved,
        m_mongo_client,
    ):
        m_poller.return_value = None
        from splunk_connect_for_snmp.snmp.tasks import trap

        m_time.return_value = 1640692955.365186
        m_resolved.side_effect = SmiError()
        m_is_mib_known.return_value = (False, "")
        numeric_oid = "1.3.6.1.4.1.99999.1.2.3"

        work = {"data": [(numeric_oid, "value")], "host": "192.168.0.1"}
        m_process_data.return_value = (
            False,
            [],
            {"SNMPv2-MIB::tuple=int=0": {"metrics": {}, "fields": {}, "indexes": []}},
        )
        m_poller.trap = trap
        m_poller.trap.mib_view_controller = MagicMock()
        m_poller.trap.already_loaded_mibs = set()
        result = trap(work)

        unresolved = result["result"]["sc4snmp::unresolved"]["fields"]
        self.assertIn(f"unresolved::{numeric_oid}", unresolved)
        self.assertEqual(numeric_oid, unresolved[f"unresolved::{numeric_oid}"]["oid"])
        m_load_mib.assert_not_called()

    @patch("pysnmp.smi.rfc1902.ObjectType.resolveWithMib")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.process_snmp_data")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.is_mib_known")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.load_mibs")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.__init__")
    @patch("time.time")
    def test_trap_retries_remaining_oids_when_mib_already_loaded(
        self,
        m_time,
        m_poller,
        m_load_mib,
        m_is_mib_known,
        m_process_data,
        m_resolved,
        m_mongo_client,
    ):
        m_poller.return_value = None
        from splunk_connect_for_snmp.snmp.tasks import trap

        m_time.return_value = 1640692955.365186
        numeric_oid = "1.3.6.1.4.1.9.9.513.1.1.1.1.1.6.0"
        m_resolved.side_effect = [SmiError, "RETRY_OK"]
        m_is_mib_known.return_value = (True, "CISCO-LWAPP-AP-MIB")

        work = {"data": [(numeric_oid, "17")], "host": "192.168.0.1"}
        m_process_data.return_value = (False, [], {"test": "value1"})
        m_poller.trap = trap
        m_poller.trap.mib_view_controller = MagicMock()
        m_poller.trap.mib_view_controller.get_node_location.side_effect = (
            NoSuchObjectError()
        )
        m_poller.trap.already_loaded_mibs = {"CISCO-LWAPP-AP-MIB"}
        trap(work)

        self.assertEqual(2, m_resolved.call_count)
        m_load_mib.assert_not_called()

    @patch("pysnmp.smi.rfc1902.ObjectType.resolveWithMib")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.process_snmp_data")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.is_mib_known")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.load_mibs")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.__init__")
    @patch("time.time")
    def test_trap_preloads_mib_from_numeric_varbind_name(
        self,
        m_time,
        m_poller,
        m_load_mib,
        m_is_mib_known,
        m_process_data,
        m_resolved,
        m_mongo_client,
    ):
        m_poller.return_value = None
        from splunk_connect_for_snmp.snmp.tasks import trap

        m_time.return_value = 1640692955.365186
        numeric_oid = "1.3.6.1.4.1.9.9.513.1.1.1.1.1.6.0"
        m_resolved.return_value = "TEST1"
        m_is_mib_known.return_value = (True, "CISCO-LWAPP-AP-MIB")

        work = {"data": [(numeric_oid, "17")], "host": "192.168.0.1"}
        m_process_data.return_value = (False, [], {"test": "value1"})
        m_poller.trap = trap
        m_poller.trap.mib_view_controller = MagicMock()
        m_poller.trap.already_loaded_mibs = set()
        trap(work)

        m_load_mib.assert_called()
        loaded = m_load_mib.call_args_list[0][0][0]
        self.assertIn("CISCO-LWAPP-AP-MIB", loaded)

    @patch("pysnmp.smi.rfc1902.ObjectType.resolveWithMib")
    def test_resolve_trap_varbind_uses_node_location(self, m_resolved, m_mongo_client):
        from splunk_connect_for_snmp.snmp.tasks import _resolve_trap_varbind

        m_resolved.side_effect = [SmiError, "RESOLVED"]
        mock_self = MagicMock()
        mock_self.mib_view_controller.get_node_location.return_value = (
            "CISCO-LWAPP-AP-MIB",
            "cLApUpTime",
            (244, 116, 112, 116, 189, 144),
        )
        oid = "1.3.6.1.4.1.9.9.513.1.1.1.1.1.6.244.116.112.116.189.144"
        result = _resolve_trap_varbind(mock_self, oid, "12345")
        self.assertEqual("RESOLVED", result)
        self.assertEqual(2, m_resolved.call_count)

    @patch("splunk_connect_for_snmp.snmp.tasks.RESOLVE_TRAP_ADDRESS", "true")
    @patch("splunk_connect_for_snmp.snmp.tasks.resolve_address")
    @patch("pysnmp.smi.rfc1902.ObjectType.resolveWithMib")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.process_snmp_data")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.__init__")
    @patch("time.time")
    def test_trap_reverse_dns_lookup(
        self,
        m_time,
        m_poller,
        m_process_data,
        m_resolved,
        m_resolve_address,
        m_mongo_client,
    ):
        m_poller.return_value = None
        from splunk_connect_for_snmp.snmp.tasks import trap

        m_time.return_value = 1640692955.365186

        m_resolved.return_value = None
        m_resolve_address.return_value = "my.host"

        work = {"data": [("asd", "tre")], "host": "192.168.0.1"}
        m_process_data.return_value = (False, [], {"test": "value1"})
        m_poller.builder = MagicMock()
        m_poller.trap = trap
        m_poller.trap.mib_view_controller = MagicMock()
        trap.already_loaded_mibs = set()
        result = trap(work)

        self.assertEqual(
            {
                "address": "my.host",
                "detectchange": False,
                "result": {"test": "value1"},
                "sourcetype": "sc4snmp:traps",
                "time": 1640692955.365186,
            },
            result,
        )


class TestHelpers(TestCase):
    @patch("splunk_connect_for_snmp.snmp.tasks.IPv6_ENABLED")
    def test_format_ipv4_address(self, ipv6_enabled):
        from splunk_connect_for_snmp.snmp.tasks import format_ipv4_address

        ipv6_enabled.return_value = True
        ip_address = "::ffff:172.31.20.76"
        host = format_ipv4_address(ip_address)
        self.assertEqual(host, "172.31.20.76")

    def test_format_ipv4_address_disabled(self):
        from splunk_connect_for_snmp.snmp.tasks import format_ipv4_address

        ip_address = "::ffff:172.31.20.76"
        host = format_ipv4_address(ip_address)
        self.assertEqual(host, "::ffff:172.31.20.76")

    def test_format_ipv4_address_ipv6(self):
        from splunk_connect_for_snmp.snmp.tasks import format_ipv4_address

        ip_address = "fd02::b24a:409e:a35e:b580"
        host = format_ipv4_address(ip_address)
        self.assertEqual(host, "fd02::b24a:409e:a35e:b580")
