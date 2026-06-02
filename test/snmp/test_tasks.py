from unittest import TestCase
from unittest.mock import MagicMock, patch

from pysnmp.smi.error import NoSuchObjectError, SmiError
from pysnmp.smi.rfc1902 import ObjectIdentity


@patch("pymongo.MongoClient")
class TestTasks(TestCase):
    def setUp(self):
        super().setUp()
        patcher = patch("pysnmp.smi.rfc1902.ObjectIdentity.resolveWithMib")
        self.addCleanup(patcher.stop)
        self.mock_identity_resolve = patcher.start()
        resolved_identity = ObjectIdentity("1.3.6.1.2.1.1.1.0")
        mib_node = MagicMock()
        mib_node.getSyntax.return_value.clone.return_value = MagicMock()
        resolved_identity.getMibNode = MagicMock(return_value=mib_node)
        self.mock_identity_resolve.return_value = resolved_identity

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

        m_resolved.return_value = "RESOLVED"

        work = {"data": [("asd", "tre")], "host": "192.168.0.1"}
        m_process_data.return_value = (False, [], {"test": "value1"})
        m_poller.builder = MagicMock()
        m_poller.trap = trap
        m_poller.trap.mib_view_controller = MagicMock()
        trap.already_loaded_mibs = set()
        result = trap(work)

        self.assertEqual(1, m_resolved.call_count)
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

        m_resolved.return_value = "RESOLVED"

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
        m_load_mib.return_value = {"SOME-MIB"}
        work = {"data": [("asd", "tre")], "host": "192.168.0.1"}
        m_process_data.return_value = (False, [], {"test": "value1"})
        m_poller.trap = trap
        m_poller.trap.mib_view_controller = MagicMock()
        m_poller.trap.mib_view_controller.get_node_location.side_effect = (
            NoSuchObjectError()
        )
        trap.already_loaded_mibs = set()
        result = trap(work)

        calls = m_load_mib.call_args_list
        self.assertEqual(["SOME-MIB"], calls[0][0][0])

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

    @patch(
        "splunk_connect_for_snmp.snmp.tasks.INCLUDE_UNRESOLVED_TRAP_VARBINDS",
        True,
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
        m_load_mib.return_value = {"SOME-MIB"}

        work = {"data": [("asd", "tre")], "host": "192.168.0.1"}
        m_process_data.return_value = (False, [], {"test": "value1"})
        m_poller.trap = trap
        m_poller.trap.mib_view_controller = MagicMock()
        m_poller.trap.mib_view_controller.get_node_location.side_effect = (
            NoSuchObjectError()
        )
        trap.already_loaded_mibs = set()
        result = trap(work)

        calls = m_load_mib.call_args_list

        process_calls = m_process_data.call_args_list
        self.assertEqual([], process_calls[0][0][0])
        self.assertEqual(2, m_resolved.call_count)

        self.assertEqual(["SOME-MIB"], calls[0][0][0])
        self.assertEqual("192.168.0.1", result["address"])
        self.assertIn("sc4snmp::unresolved", result["result"])
        self.assertIn(
            "unresolved::asd",
            result["result"]["sc4snmp::unresolved"]["fields"],
        )

    @patch(
        "splunk_connect_for_snmp.snmp.tasks.INCLUDE_UNRESOLVED_TRAP_VARBINDS",
        True,
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
        trap.already_loaded_mibs = set()
        result = trap(work)

        unresolved = result["result"]["sc4snmp::unresolved"]["fields"]
        self.assertIn(f"unresolved::{numeric_oid}", unresolved)
        self.assertEqual(numeric_oid, unresolved[f"unresolved::{numeric_oid}"]["oid"])
        m_load_mib.assert_not_called()

    @patch(
        "splunk_connect_for_snmp.snmp.tasks.INCLUDE_UNRESOLVED_TRAP_VARBINDS",
        False,
    )
    @patch("pysnmp.smi.rfc1902.ObjectType.resolveWithMib")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.process_snmp_data")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.is_mib_known")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.load_mibs")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.__init__")
    @patch("time.time")
    def test_trap_omits_unresolved_when_disabled(
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
        trap.already_loaded_mibs = set()
        result = trap(work)

        self.assertNotIn("sc4snmp::unresolved", result["result"])
        m_load_mib.assert_not_called()

    @patch(
        "splunk_connect_for_snmp.snmp.tasks.INCLUDE_UNRESOLVED_TRAP_VARBINDS",
        False,
    )
    @patch("pysnmp.smi.rfc1902.ObjectType.resolveWithMib")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.process_snmp_data")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.is_mib_known")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.load_mibs")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.__init__")
    @patch("time.time")
    def test_trap_re_resolves_varbinds_after_process_snmp_data_mib_load(
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
        mock_oid = MagicMock()
        mock_oid.getOid.return_value = numeric_oid
        mock_oid.prettyPrint.return_value = "CISCO-LWAPP-AP-MIB::cLApUpTime"
        mock_varbind = (mock_oid, MagicMock(prettyPrint=MagicMock(return_value="17")))
        m_resolved.return_value = mock_varbind
        m_is_mib_known.return_value = (False, "")
        m_load_mib.return_value = {"CISCO-LWAPP-AP-MIB"}
        metrics_group = {
            "CISCO-LWAPP-AP-MIB::cLApUpTime": {
                "metrics": {},
                "fields": {"CISCO-LWAPP-AP-MIB.cLApUpTime": {"value": 17, "oid": numeric_oid}},
                "indexes": [],
            }
        }
        m_process_data.side_effect = [
            (True, ["CISCO-LWAPP-AP-MIB"], {}),
            (False, [], metrics_group),
        ]

        work = {"data": [(numeric_oid, "17")], "host": "192.168.0.1"}
        m_poller.trap = trap
        trap.already_loaded_mibs = set()
        m_poller.trap.mib_view_controller = MagicMock()
        result = trap(work)

        self.assertIn("CISCO-LWAPP-AP-MIB::cLApUpTime", result["result"])
        self.assertNotIn("sc4snmp::unresolved", result["result"])
        self.assertEqual(2, m_process_data.call_count)
        self.assertEqual(1, m_load_mib.call_count)
        self.assertGreater(len(m_process_data.call_args_list[1][0][0]), 0)

    @patch(
        "splunk_connect_for_snmp.snmp.tasks.INCLUDE_UNRESOLVED_TRAP_VARBINDS",
        False,
    )
    @patch("pysnmp.smi.rfc1902.ObjectType.resolveWithMib")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.process_snmp_data")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.is_mib_known")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.load_mibs")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.__init__")
    @patch("time.time")
    def test_trap_re_resolves_pseudo_resolved_varbinds_before_metrics(
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
        pseudo_oid = MagicMock()
        pseudo_oid.getOid.return_value = numeric_oid
        pseudo_oid.prettyPrint.return_value = (
            "SNMPv2-SMI::enterprises.9.9.513.1.1.1.1.1.6.0"
        )
        good_oid = MagicMock()
        good_oid.getOid.return_value = numeric_oid
        good_oid.prettyPrint.return_value = "CISCO-LWAPP-AP-MIB::cLApUpTime"
        pseudo_varbind = (
            pseudo_oid,
            MagicMock(prettyPrint=MagicMock(return_value="17")),
        )
        good_varbind = (good_oid, MagicMock(prettyPrint=MagicMock(return_value="17")))
        m_resolved.side_effect = [pseudo_varbind, good_varbind]
        m_is_mib_known.return_value = (False, "")
        metrics_group = {
            "CISCO-LWAPP-AP-MIB::cLApUpTime": {
                "metrics": {},
                "fields": {"CISCO-LWAPP-AP-MIB.cLApUpTime": {"value": 17, "oid": numeric_oid}},
                "indexes": [],
            }
        }
        m_process_data.return_value = (False, [], metrics_group)

        work = {"data": [(numeric_oid, "17")], "host": "192.168.0.1"}
        m_poller.trap = trap
        trap.already_loaded_mibs = {"CISCO-LWAPP-AP-MIB"}
        m_poller.trap.mib_view_controller = MagicMock()
        result = trap(work)

        self.assertIn("CISCO-LWAPP-AP-MIB::cLApUpTime", result["result"])
        self.assertEqual(2, m_resolved.call_count)
        self.assertEqual(
            "CISCO-LWAPP-AP-MIB::cLApUpTime",
            m_process_data.call_args[0][0][0][0].prettyPrint(),
        )
        m_load_mib.assert_not_called()

    @patch(
        "splunk_connect_for_snmp.snmp.tasks.INCLUDE_UNRESOLVED_TRAP_VARBINDS",
        False,
    )
    @patch("pysnmp.smi.rfc1902.ObjectType.resolveWithMib")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.process_snmp_data")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.is_mib_known")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.load_mibs")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.__init__")
    @patch("time.time")
    @patch(
        "splunk_connect_for_snmp.snmp.tasks._re_resolve_trap_work_if_needed",
        side_effect=lambda self, work_data, varbind_table, unresolved: (
            varbind_table,
            unresolved,
        ),
    )
    def test_trap_process_snmp_data_no_spin_when_mib_already_loaded(
        self,
        m_skip_pre_metrics_re_resolve,
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
        pseudo_oid = MagicMock()
        pseudo_oid.getOid.return_value = numeric_oid
        pseudo_oid.prettyPrint.return_value = (
            "SNMPv2-SMI::enterprises.9.9.513.1.1.1.1.1.6.0"
        )
        good_oid = MagicMock()
        good_oid.getOid.return_value = numeric_oid
        good_oid.prettyPrint.return_value = "CISCO-LWAPP-AP-MIB::cLApUpTime"
        pseudo_varbind = (
            pseudo_oid,
            MagicMock(prettyPrint=MagicMock(return_value="17")),
        )
        good_varbind = (good_oid, MagicMock(prettyPrint=MagicMock(return_value="17")))
        m_resolved.side_effect = [pseudo_varbind, good_varbind]
        m_is_mib_known.return_value = (True, "CISCO-LWAPP-AP-MIB")
        metrics_group = {
            "CISCO-LWAPP-AP-MIB::cLApUpTime": {
                "metrics": {},
                "fields": {"CISCO-LWAPP-AP-MIB.cLApUpTime": {"value": 17, "oid": numeric_oid}},
                "indexes": [],
            }
        }
        m_process_data.side_effect = [
            (True, ["CISCO-LWAPP-AP-MIB"], {}),
            (False, [], metrics_group),
        ]

        work = {"data": [(numeric_oid, "17")], "host": "192.168.0.1"}
        m_poller.trap = trap
        trap.already_loaded_mibs = {"CISCO-LWAPP-AP-MIB"}
        m_poller.trap.mib_view_controller = MagicMock()
        result = trap(work)

        self.assertIn("CISCO-LWAPP-AP-MIB::cLApUpTime", result["result"])
        self.assertEqual(2, m_process_data.call_count)
        m_load_mib.assert_not_called()

    @patch(
        "splunk_connect_for_snmp.snmp.tasks.INCLUDE_UNRESOLVED_TRAP_VARBINDS",
        True,
    )
    @patch("pysnmp.smi.rfc1902.ObjectType.resolveWithMib")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.process_snmp_data")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.is_mib_known")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.load_mibs")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.__init__")
    @patch("time.time")
    def test_trap_includes_unprocessed_varbinds_when_metrics_empty(
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
        mock_oid = MagicMock()
        mock_oid.getOid.return_value = numeric_oid
        mock_oid.prettyPrint.return_value = numeric_oid
        mock_varbind = (mock_oid, MagicMock(prettyPrint=MagicMock(return_value="17")))
        m_resolved.side_effect = SmiError()
        m_is_mib_known.return_value = (True, "CISCO-LWAPP-AP-MIB")
        m_load_mib.return_value = {"CISCO-LWAPP-AP-MIB"}

        work = {"data": [(numeric_oid, "17")], "host": "192.168.0.1"}
        m_process_data.return_value = (False, [], {})
        m_poller.trap = trap
        trap.already_loaded_mibs = set()
        m_poller.trap.mib_view_controller = MagicMock()
        m_poller.trap.mib_view_controller.get_node_location.side_effect = (
            NoSuchObjectError()
        )
        result = trap(work)

        self.assertEqual(1, m_resolved.call_count)
        unresolved = result["result"]["sc4snmp::unresolved"]["fields"]
        self.assertIn(f"unresolved::{numeric_oid}", unresolved)
        self.assertEqual(17, unresolved[f"unresolved::{numeric_oid}"]["value"])

    @patch("pysnmp.smi.rfc1902.ObjectType.resolveWithMib")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.process_snmp_data")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.is_mib_known")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.load_mibs")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.__init__")
    @patch("time.time")
    def test_trap_retries_when_mib_load_returns_empty(
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
        m_resolved.side_effect = [SmiError, SmiError, "RETRY_OK"]
        m_is_mib_known.return_value = (True, "CISCO-LWAPP-AP-MIB")
        m_load_mib.return_value = set()

        work = {"data": [(numeric_oid, "17")], "host": "192.168.0.1"}
        m_process_data.return_value = (False, [], {"test": "value1"})
        m_poller.trap = trap
        trap.already_loaded_mibs = set()
        m_poller.trap.mib_view_controller = MagicMock()
        m_poller.trap.mib_view_controller.get_node_location.side_effect = (
            NoSuchObjectError()
        )
        trap(work)

        self.assertGreaterEqual(m_load_mib.call_count, 2)
        self.assertNotIn("CISCO-LWAPP-AP-MIB", trap.already_loaded_mibs)

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
        m_load_mib.return_value = {"CISCO-LWAPP-AP-MIB"}

        work = {"data": [(numeric_oid, "17")], "host": "192.168.0.1"}
        m_process_data.return_value = (False, [], {"test": "value1"})
        m_poller.trap = trap
        m_poller.trap.mib_view_controller = MagicMock()
        trap.already_loaded_mibs = set()
        trap(work)

        m_load_mib.assert_called()
        loaded = m_load_mib.call_args_list[0][0][0]
        self.assertIn("CISCO-LWAPP-AP-MIB", loaded)
        self.assertEqual(1, m_resolved.call_count)

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

        m_resolved.return_value = "RESOLVED"
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


class TestTrapVarbindResolveValue(TestCase):
    def test_empty_string_uses_unspecified(self):
        from pysnmp.proto import rfc1905

        from splunk_connect_for_snmp.snmp.tasks import _value_for_trap_resolve

        value = _value_for_trap_resolve("")
        self.assertIs(value, rfc1905.unSpecified)

    def test_non_empty_string_unchanged(self):
        from splunk_connect_for_snmp.snmp.tasks import _value_for_trap_resolve

        self.assertEqual("10.1.1.1", _value_for_trap_resolve("10.1.1.1"))


class TestTrapVarbindCoercion(TestCase):
    def setUp(self):
        super().setUp()
        patcher = patch("pysnmp.smi.rfc1902.ObjectIdentity.resolveWithMib")
        self.addCleanup(patcher.stop)
        self.mock_identity_resolve = patcher.start()
        resolved_identity = MagicMock()
        resolved_identity.getMibNode.return_value = MagicMock()
        self.mock_identity_resolve.return_value = resolved_identity

    def test_coerce_wraps_plain_integer_for_notification_nodes(self):
        from pysnmp.proto import rfc1902

        from splunk_connect_for_snmp.snmp.tasks import _coerce_trap_varbind_value

        class _NodeWithoutSyntax:
            def getSyntax(self):
                raise TypeError("notification")

        value = _coerce_trap_varbind_value(0, _NodeWithoutSyntax())
        self.assertIsInstance(value, rfc1902.Integer)
        self.assertEqual(0, int(value))

    def test_coerce_uses_mib_syntax_when_available(self):
        from pysnmp.proto.rfc1902 import OctetString

        from splunk_connect_for_snmp.snmp.tasks import _coerce_trap_varbind_value

        class _NodeWithSyntax:
            def getSyntax(self):
                return OctetString

        value = _coerce_trap_varbind_value("10.1.1.1", _NodeWithSyntax())
        self.assertTrue(
            isinstance(value, OctetString) or value == "10.1.1.1",
            msg=f"expected OctetString or str, got {type(value)}",
        )

    def test_coerce_keeps_text_string_for_string_syntax(self):
        from splunk_connect_for_snmp.snmp.tasks import _coerce_trap_varbind_value

        class _NodeWithOctetSyntax:
            def getSyntax(self):
                from pysnmp.proto.rfc1902 import OctetString

                return OctetString

        from pysnmp.proto import rfc1902

        value = _coerce_trap_varbind_value("configured", _NodeWithOctetSyntax())
        self.assertNotIsInstance(value, rfc1902.Integer)

    @patch("splunk_connect_for_snmp.snmp.tasks.ObjectType")
    @patch("splunk_connect_for_snmp.snmp.tasks.ObjectIdentity")
    def test_object_type_from_resolved_identity_coerces_plain_zero(
        self, m_identity_cls, m_object_type_cls
    ):
        from pysnmp.proto import rfc1902

        from splunk_connect_for_snmp.snmp.tasks import (
            _object_type_from_resolved_identity,
        )

        resolved_identity = MagicMock()
        m_identity_cls.return_value.resolveWithMib.return_value = resolved_identity
        mib_node = MagicMock()
        mib_node.__class__.__name__ = "NotificationType"
        mib_node.getSyntax.side_effect = TypeError("notification")
        resolved_identity.getMibNode.return_value = mib_node
        m_object_type_cls.return_value.resolveWithMib.return_value = "object_type"
        mib_view = MagicMock()

        result = _object_type_from_resolved_identity(
            mib_view, "SNMPv2-MIB::snmpTrapOID.0", 0
        )
        self.assertEqual("object_type", result)
        coerced_value = m_object_type_cls.call_args[0][1]
        self.assertIsInstance(coerced_value, rfc1902.Integer)
        self.assertEqual(0, int(coerced_value))


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
