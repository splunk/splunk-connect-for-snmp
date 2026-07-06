import time
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from splunk_connect_for_snmp.common.inventory_record import InventoryRecord
from splunk_connect_for_snmp.snmp.exceptions import SnmpActionError
from splunk_connect_for_snmp.snmp.manager import Poller
from splunk_connect_for_snmp.snmp.varbinds_resolver import ProfileCollection

inventory_record = InventoryRecord(
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

inventory_record_with_max_oid = InventoryRecord(
    **{
        "address": "192.168.0.1",
        "port": "34",
        "version": "2c",
        "community": "public",
        "secret": "secret",
        "securityEngine": "ENGINE",
        "walk_interval": 1850,
        "max_oid_to_process": 5,
        "profiles": "",
        "SmartProfiles": True,
        "delete": False,
    }
)


class TestDoWork(IsolatedAsyncioTestCase):
    @patch("pymongo.MongoClient", MagicMock())
    @patch("mongolock.MongoLock.__init__", MagicMock())
    @patch("mongolock.MongoLock.lock", MagicMock())
    @patch("mongolock.MongoLock.release", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.get_auth", new_callable=AsyncMock)
    @patch("splunk_connect_for_snmp.snmp.manager.get_context_data", MagicMock())
    @patch(
        "splunk_connect_for_snmp.snmp.manager.setup_transport_target",
        new_callable=AsyncMock,
    )
    async def test_do_work_no_work_to_do(self, setup_transport, get_auth):
        poller = Poller.__new__(Poller)
        poller.last_modified = time.time()
        poller.snmp_engine = None
        poller.profiles_manager = MagicMock()
        poller.profiles_collection = MagicMock()
        poller.profiles_collection.process_profiles = MagicMock()
        poller.already_loaded_mibs = set()
        varbinds_bulk, varbinds_get = set(), set()
        get_mapping, bulk_mapping = {}, {}

        poller.get_varbinds = MagicMock(
            return_value=(varbinds_get, get_mapping, varbinds_bulk, bulk_mapping)
        )
        result = await poller.do_work(inventory_record)
        self.assertEqual(result, (False, {}))

    @patch("mongolock.MongoLock.__init__", MagicMock())
    @patch("mongolock.MongoLock.lock", MagicMock())
    @patch("mongolock.MongoLock.release", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.get_auth", new_callable=AsyncMock)
    @patch("splunk_connect_for_snmp.snmp.manager.get_context_data", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.get_snmp_engine", MagicMock())
    @patch(
        "splunk_connect_for_snmp.snmp.manager.setup_transport_target",
        new_callable=AsyncMock,
    )
    @patch("splunk_connect_for_snmp.snmp.manager.multi_bulk_walk_cmd")
    @patch("splunk_connect_for_snmp.snmp.manager.get_cmd", new_callable=AsyncMock)
    async def test_do_work_bulk(
        self,
        get_cmd,
        multi_bulk_walk_cmd,
        setup_transport_target,
        get_auth,
    ):
        poller = Poller.__new__(Poller)
        poller.last_modified = time.time()
        poller.snmp_engine = None
        poller.builder = MagicMock()
        poller.mib_view_controller = MagicMock()
        poller.profiles_manager = MagicMock()
        poller.process_snmp_data = MagicMock(return_value=(False, [], {}))

        requested_profiles = ["profile1", "profile2"]
        poller.profiles = {
            "profile1": {
                "frequency": 20,
                "varBinds": [["IF-MIB", "ifDescr"], ["IF-MIB", "ifSpeed"]],
            },
            "profile2": {"frequency": 20, "varBinds": [["UDP-MIB", "udpOutDatagrams"]]},
        }
        poller.already_loaded_mibs = set()
        poller.profiles_collection = ProfileCollection(poller.profiles)
        poller.profiles_collection.process_profiles()

        def multi_bulk_walk_cmd_mock(*args, **kwargs):
            async def _gen():
                yield (None, 0, 0, ["Oid1"])
                yield (None, 0, 0, ["Oid2"])

            return _gen()

        multi_bulk_walk_cmd.side_effect = multi_bulk_walk_cmd_mock
        get_auth.return_value = MagicMock()
        setup_transport_target.return_value = MagicMock()

        await poller.do_work(inventory_record, profiles=requested_profiles)

        self.assertEqual(poller.process_snmp_data.call_count, 2)
        get_cmd.assert_not_called()
        self.assertEqual(multi_bulk_walk_cmd.call_count, 1)

    @patch("mongolock.MongoLock.__init__", MagicMock())
    @patch("mongolock.MongoLock.lock", MagicMock())
    @patch("mongolock.MongoLock.release", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.get_auth", new_callable=AsyncMock)
    @patch("splunk_connect_for_snmp.snmp.manager.get_context_data", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.get_snmp_engine", MagicMock())
    @patch(
        "splunk_connect_for_snmp.snmp.manager.setup_transport_target",
        new_callable=AsyncMock,
    )
    @patch("splunk_connect_for_snmp.snmp.manager.multi_bulk_walk_cmd")
    @patch("splunk_connect_for_snmp.snmp.manager.get_cmd", new_callable=AsyncMock)
    async def test_do_work_get(
        self,
        get_cmd,
        multi_bulk_walk_cmd,
        setup_transport_target,
        get_auth,
    ):
        poller = Poller.__new__(Poller)
        poller.last_modified = time.time()
        poller.snmp_engine = None
        poller.builder = MagicMock()
        poller.mib_view_controller = MagicMock()
        poller.process_snmp_data = MagicMock()
        poller.profiles_manager = MagicMock()
        requested_profiles = ["profile1", "profile2"]
        poller.profiles = {
            "profile1": {
                "frequency": 20,
                "varBinds": [["IF-MIB", "ifDescr", 1], ["IF-MIB", "ifSpeed", 2]],
            },
            "profile2": {
                "frequency": 20,
                "varBinds": [["UDP-MIB", "udpOutDatagrams", 1]],
            },
        }
        poller.already_loaded_mibs = set()
        poller.profiles_collection = ProfileCollection(poller.profiles)
        poller.profiles_collection.process_profiles()
        get_cmd.return_value = (None, 0, 0, ["Oid1", "Oid2", "Oid3"])
        await poller.do_work(inventory_record, profiles=requested_profiles)
        self.assertEqual(poller.process_snmp_data.call_count, 1)
        self.assertEqual(get_cmd.call_count, 1)
        self.assertEqual(multi_bulk_walk_cmd.call_count, 0)

    @patch("pymongo.MongoClient", MagicMock())
    @patch("mongolock.MongoLock.__init__", MagicMock())
    @patch("mongolock.MongoLock.lock", MagicMock())
    @patch("mongolock.MongoLock.release", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.get_auth", new_callable=AsyncMock)
    @patch("splunk_connect_for_snmp.snmp.manager.get_context_data", MagicMock())
    @patch(
        "splunk_connect_for_snmp.snmp.manager.setup_transport_target",
        new_callable=AsyncMock,
    )
    @patch("splunk_connect_for_snmp.snmp.manager.multi_bulk_walk_cmd")
    @patch("splunk_connect_for_snmp.snmp.manager.get_cmd", new_callable=AsyncMock)
    async def test_do_work_errors(
        self,
        get_cmd_mock,
        multi_bulk_walk_cmd_mock,
        setup_transport_target,
        get_auth,
    ):
        poller = Poller.__new__(Poller)
        poller.last_modified = time.time()
        poller.snmp_engine = None
        poller.builder = MagicMock()
        poller.mib_view_controller = MagicMock()
        poller.process_snmp_data = MagicMock()
        poller.profiles_manager = MagicMock()
        requested_profiles = ["profile1"]
        poller.profiles = {
            "profile1": {"frequency": 20, "varBinds": [["IF-MIB", "ifDescr", 1]]}
        }
        poller.already_loaded_mibs = set()
        poller.profiles_collection = ProfileCollection(poller.profiles)
        poller.profiles_collection.process_profiles()

        async def get_cmd_failure(*args, **kwargs):
            return (True, True, 2, [])

        get_cmd_mock.side_effect = get_cmd_failure
        with self.assertRaises(SnmpActionError):
            await poller.do_work(inventory_record, profiles=requested_profiles)
        self.assertEqual(poller.process_snmp_data.call_count, 0)
        self.assertEqual(get_cmd_mock.call_count, 1)
        self.assertEqual(multi_bulk_walk_cmd_mock.call_count, 0)

    @patch("mongolock.MongoLock.__init__", MagicMock())
    @patch("mongolock.MongoLock.lock", MagicMock())
    @patch("mongolock.MongoLock.release", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.get_auth", new_callable=AsyncMock)
    @patch("splunk_connect_for_snmp.snmp.manager.get_context_data", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.get_snmp_engine", MagicMock())
    @patch(
        "splunk_connect_for_snmp.snmp.manager.setup_transport_target",
        new_callable=AsyncMock,
    )
    @patch("splunk_connect_for_snmp.snmp.manager.multi_bulk_walk_cmd")
    @patch("splunk_connect_for_snmp.snmp.manager.get_cmd", new_callable=AsyncMock)
    async def test_do_work_bulk_uses_per_device_max_oid(
        self,
        get_cmd,
        multi_bulk_walk_cmd,
        setup_transport_target,
        get_auth,
    ):
        poller = Poller.__new__(Poller)
        poller.last_modified = time.time()
        poller.snmp_engine = None
        poller.builder = MagicMock()
        poller.process_snmp_data = MagicMock(return_value=(False, [], {}))
        poller.profiles_manager = MagicMock()
        requested_profiles = ["profile1", "profile2"]
        poller.profiles = {
            "profile1": {
                "frequency": 20,
                "varBinds": [["IF-MIB", "ifDescr"], ["IF-MIB", "ifSpeed"]],
            },
            "profile2": {"frequency": 20, "varBinds": [["UDP-MIB", "udpOutDatagrams"]]},
        }
        poller.already_loaded_mibs = set()
        poller.profiles_collection = ProfileCollection(poller.profiles)
        poller.profiles_collection.process_profiles()
        poller.get_varbind_chunk = MagicMock(wraps=poller.get_varbind_chunk)

        def multi_bulk_walk_cmd_mock(*args, **kwargs):
            async def _gen():
                yield (None, 0, 0, ["Oid1"])

            return _gen()

        multi_bulk_walk_cmd.side_effect = multi_bulk_walk_cmd_mock

        await poller.do_work(inventory_record_with_max_oid, profiles=requested_profiles)

        self.assertEqual(poller.get_varbind_chunk.call_args.args[1], 5)
        self.assertEqual(multi_bulk_walk_cmd.call_count, 1)
        get_cmd.assert_not_called()

    @patch("mongolock.MongoLock.__init__", MagicMock())
    @patch("mongolock.MongoLock.lock", MagicMock())
    @patch("mongolock.MongoLock.release", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.get_auth", new_callable=AsyncMock)
    @patch("splunk_connect_for_snmp.snmp.manager.get_context_data", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.get_snmp_engine", MagicMock())
    @patch(
        "splunk_connect_for_snmp.snmp.manager.setup_transport_target",
        new_callable=AsyncMock,
    )
    @patch("splunk_connect_for_snmp.snmp.manager.multi_bulk_walk_cmd")
    @patch("splunk_connect_for_snmp.snmp.manager.get_cmd", new_callable=AsyncMock)
    async def test_do_work_get_uses_per_device_max_oid(
        self,
        get_cmd,
        multi_bulk_walk_cmd,
        setup_transport_target,
        get_auth,
    ):
        poller = Poller.__new__(Poller)
        poller.last_modified = time.time()
        poller.snmp_engine = None
        poller.builder = MagicMock()
        poller.process_snmp_data = MagicMock()
        poller.profiles_manager = MagicMock()
        requested_profiles = ["profile1", "profile2"]
        poller.profiles = {
            "profile1": {
                "frequency": 20,
                "varBinds": [["IF-MIB", "ifDescr", 1], ["IF-MIB", "ifSpeed", 2]],
            },
            "profile2": {
                "frequency": 20,
                "varBinds": [["UDP-MIB", "udpOutDatagrams", 1]],
            },
        }
        poller.already_loaded_mibs = set()
        poller.profiles_collection = ProfileCollection(poller.profiles)
        poller.profiles_collection.process_profiles()
        poller.get_varbind_chunk = MagicMock(wraps=poller.get_varbind_chunk)
        get_cmd.return_value = (None, 0, 0, ["Oid1", "Oid2", "Oid3"])

        await poller.do_work(inventory_record_with_max_oid, profiles=requested_profiles)

        self.assertEqual(poller.get_varbind_chunk.call_args.args[1], 5)
        self.assertEqual(poller.process_snmp_data.call_count, 1)
        self.assertEqual(get_cmd.call_count, 1)
        multi_bulk_walk_cmd.assert_not_called()

    @patch("mongolock.MongoLock.__init__", MagicMock())
    @patch("mongolock.MongoLock.lock", MagicMock())
    @patch("mongolock.MongoLock.release", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.get_auth", new_callable=AsyncMock)
    @patch("splunk_connect_for_snmp.snmp.manager.get_context_data", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.get_snmp_engine", MagicMock())
    @patch(
        "splunk_connect_for_snmp.snmp.manager.setup_transport_target",
        new_callable=AsyncMock,
    )
    @patch("splunk_connect_for_snmp.snmp.manager.MAX_OID_TO_PROCESS", 70)
    @patch("splunk_connect_for_snmp.snmp.manager.multi_bulk_walk_cmd")
    @patch("splunk_connect_for_snmp.snmp.manager.get_cmd", new_callable=AsyncMock)
    async def test_do_work_bulk_falls_back_to_global_max_oid(
        self,
        get_cmd,
        multi_bulk_walk_cmd,
        setup_transport_target,
        get_auth,
    ):
        poller = Poller.__new__(Poller)
        poller.last_modified = time.time()
        poller.snmp_engine = None
        poller.builder = MagicMock()
        poller.process_snmp_data = MagicMock(return_value=(False, [], {}))
        poller.profiles_manager = MagicMock()
        requested_profiles = ["profile1", "profile2"]
        poller.profiles = {
            "profile1": {
                "frequency": 20,
                "varBinds": [["IF-MIB", "ifDescr"], ["IF-MIB", "ifSpeed"]],
            },
            "profile2": {"frequency": 20, "varBinds": [["UDP-MIB", "udpOutDatagrams"]]},
        }
        poller.already_loaded_mibs = set()
        poller.profiles_collection = ProfileCollection(poller.profiles)
        poller.profiles_collection.process_profiles()
        poller.get_varbind_chunk = MagicMock(wraps=poller.get_varbind_chunk)

        def multi_bulk_walk_cmd_mock(*args, **kwargs):
            async def _gen():
                yield (None, 0, 0, ["Oid1"])

            return _gen()

        multi_bulk_walk_cmd.side_effect = multi_bulk_walk_cmd_mock

        await poller.do_work(inventory_record, profiles=requested_profiles)

        self.assertEqual(poller.get_varbind_chunk.call_args.args[1], 70)
        self.assertEqual(multi_bulk_walk_cmd.call_count, 1)
        get_cmd.assert_not_called()


class TestGetVarbindChunk(TestCase):
    def test_chunk_splits_list(self):
        poller = Poller.__new__(Poller)
        items = list(range(10))
        chunks = list(poller.get_varbind_chunk(items, 3))
        self.assertEqual(chunks, [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]])

    def test_chunk_single_chunk(self):
        poller = Poller.__new__(Poller)
        items = list(range(5))
        chunks = list(poller.get_varbind_chunk(items, 10))
        self.assertEqual(chunks, [[0, 1, 2, 3, 4]])

    def test_chunk_exact_split(self):
        poller = Poller.__new__(Poller)
        items = list(range(6))
        chunks = list(poller.get_varbind_chunk(items, 3))
        self.assertEqual(chunks, [[0, 1, 2], [3, 4, 5]])

    def test_chunk_empty_list(self):
        poller = Poller.__new__(Poller)
        items = []
        chunks = list(poller.get_varbind_chunk(items, 5))
        self.assertEqual(chunks, [])
