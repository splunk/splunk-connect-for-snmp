from unittest import TestCase
from unittest.mock import MagicMock, call, patch

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


class TestDoWork(TestCase):
    @patch("pymongo.MongoClient", MagicMock())
    @patch("mongolock.MongoLock.__init__", MagicMock())
    @patch("mongolock.MongoLock.lock", MagicMock())
    @patch("mongolock.MongoLock.release", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.auth.get_auth", None)
    @patch("splunk_connect_for_snmp.snmp.manager.get_context_data", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.setup_transport_target", MagicMock())
    def test_do_work_no_work_to_do(self):
        poller = Poller.__new__(Poller)
        poller.last_modified = 1609675634
        poller.snmp_engine = None
        poller.profiles_manager = MagicMock()
        poller.profiles_collection = MagicMock()
        poller.profiles_collection.process_profiles = MagicMock()
        poller.already_loaded_mibs = {}
        varbinds_bulk, varbinds_get = set(), set()
        get_mapping, bulk_mapping = {}, {}

        poller.get_varbinds = MagicMock()
        poller.get_varbinds.return_value = (
            varbinds_get,
            get_mapping,
            varbinds_bulk,
            bulk_mapping,
        )
        result = poller.do_work(inventory_record)
        self.assertEqual(result, (False, {}))

    @patch("pymongo.MongoClient", MagicMock())
    @patch("mongolock.MongoLock.__init__", MagicMock())
    @patch("mongolock.MongoLock.lock", MagicMock())
    @patch("mongolock.MongoLock.release", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.auth.get_auth", None)
    @patch("splunk_connect_for_snmp.snmp.manager.get_context_data", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.get_snmp_engine", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.setup_transport_target", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.bulkCmd")
    @patch("splunk_connect_for_snmp.snmp.manager.getCmd")
    @patch("splunk_connect_for_snmp.common.collection_manager.ProfilesManager")
    def test_do_work_bulk(self, load_profiles, getCmd, bulkCmd):
        poller = Poller.__new__(Poller)
        poller.last_modified = 1609675634
        poller.snmp_engine = None
        poller.builder = MagicMock()
        poller.profiles_manager = MagicMock()
        m_process_data = MagicMock()
        m_process_data.return_value = (False, [], {})
        poller.process_snmp_data = m_process_data
        requested_profiles = ["profile1", "profile2"]
        poller.profiles = {
            "profile1": {
                "frequency": 20,
                "varBinds": [["IF-MIB", "ifDescr"], ["IF-MIB", "ifSpeed"]],
            },
            "profile2": {"frequency": 20, "varBinds": [["UDP-MIB", "udpOutDatagrams"]]},
        }
        poller.already_loaded_mibs = {}
        poller.profiles_collection = ProfileCollection(poller.profiles)
        poller.profiles_collection.process_profiles()
        bulkCmd.return_value = [(None, 0, 0, "Oid1"), (None, 0, 0, "Oid2")]
        poller.do_work(inventory_record, profiles=requested_profiles)
        self.assertEqual(poller.process_snmp_data.call_count, 2)
        self.assertEqual(getCmd.call_count, 0)
        self.assertEqual(bulkCmd.call_count, 1)

    @patch("pymongo.MongoClient", MagicMock())
    @patch("mongolock.MongoLock.__init__", MagicMock())
    @patch("mongolock.MongoLock.lock", MagicMock())
    @patch("mongolock.MongoLock.release", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.auth.get_auth", None)
    @patch("splunk_connect_for_snmp.snmp.manager.get_context_data", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.get_snmp_engine", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.setup_transport_target", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.bulkCmd")
    @patch("splunk_connect_for_snmp.snmp.manager.getCmd")
    @patch(
        "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.return_collection"
    )
    def test_do_work_get(self, load_profiles, getCmd, bulkCmd):
        poller = Poller.__new__(Poller)
        poller.last_modified = 1609675634
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
        poller.already_loaded_mibs = {}
        poller.profiles_collection = ProfileCollection(poller.profiles)
        poller.profiles_collection.process_profiles()
        getCmd.return_value = [
            (None, 0, 0, "Oid1"),
            (None, 0, 0, "Oid2"),
            (None, 0, 0, "Oid3"),
        ]
        poller.do_work(inventory_record, profiles=requested_profiles)
        self.assertEqual(poller.process_snmp_data.call_count, 3)
        self.assertEqual(getCmd.call_count, 1)
        self.assertEqual(bulkCmd.call_count, 0)

    @patch("pymongo.MongoClient", MagicMock())
    @patch("mongolock.MongoLock.__init__", MagicMock())
    @patch("mongolock.MongoLock.lock", MagicMock())
    @patch("mongolock.MongoLock.release", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.auth.get_auth", None)
    @patch("splunk_connect_for_snmp.snmp.manager.get_context_data", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.get_snmp_engine", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.setup_transport_target", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.bulkCmd")
    @patch("splunk_connect_for_snmp.snmp.manager.getCmd")
    @patch(
        "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.return_collection"
    )
    def test_do_work_errors(self, load_profiles, getCmd, bulkCmd):
        poller = Poller.__new__(Poller)
        poller.last_modified = 1609675634
        poller.snmp_engine = None
        poller.builder = MagicMock()
        poller.process_snmp_data = MagicMock()
        poller.profiles_manager = MagicMock()
        requested_profiles = ["profile1"]
        poller.profiles = {
            "profile1": {"frequency": 20, "varBinds": [["IF-MIB", "ifDescr", 1]]}
        }
        poller.already_loaded_mibs = {}
        poller.profiles_collection = ProfileCollection(poller.profiles)
        poller.profiles_collection.process_profiles()
        getCmd.return_value = [(True, True, 2, [])]
        with self.assertRaises(SnmpActionError):
            poller.do_work(inventory_record, profiles=requested_profiles)
        self.assertEqual(poller.process_snmp_data.call_count, 0)
        self.assertEqual(getCmd.call_count, 1)
        self.assertEqual(bulkCmd.call_count, 0)

    @patch("pymongo.MongoClient", MagicMock())
    @patch("mongolock.MongoLock.__init__", MagicMock())
    @patch("mongolock.MongoLock.lock", MagicMock())
    @patch("mongolock.MongoLock.release", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.auth.get_auth", None)
    @patch("splunk_connect_for_snmp.snmp.manager.get_context_data", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.get_snmp_engine", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.setup_transport_target", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.bulkCmd")
    @patch("splunk_connect_for_snmp.snmp.manager.getCmd")
    @patch("splunk_connect_for_snmp.common.collection_manager.ProfilesManager")
    def test_do_work_bulk_uses_per_device_max_oid(self, load_profiles, getCmd, bulkCmd):
        poller = Poller.__new__(Poller)
        poller.last_modified = 1609675634
        poller.snmp_engine = None
        poller.builder = MagicMock()
        m_process_data = MagicMock()
        m_process_data.return_value = (False, [], {})
        poller.process_snmp_data = m_process_data
        poller.profiles_manager = MagicMock()
        requested_profiles = ["profile1", "profile2"]
        poller.profiles = {
            "profile1": {
                "frequency": 20,
                "varBinds": [["IF-MIB", "ifDescr"], ["IF-MIB", "ifSpeed"]],
            },
            "profile2": {"frequency": 20, "varBinds": [["UDP-MIB", "udpOutDatagrams"]]},
        }
        poller.already_loaded_mibs = {}
        poller.profiles_collection = ProfileCollection(poller.profiles)
        poller.profiles_collection.process_profiles()
        bulkCmd.return_value = [(None, 0, 0, "Oid1")]
        poller.do_work(inventory_record_with_max_oid, profiles=requested_profiles)
        self.assertEqual(bulkCmd.call_count, 1)

    @patch("pymongo.MongoClient", MagicMock())
    @patch("mongolock.MongoLock.__init__", MagicMock())
    @patch("mongolock.MongoLock.lock", MagicMock())
    @patch("mongolock.MongoLock.release", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.auth.get_auth", None)
    @patch("splunk_connect_for_snmp.snmp.manager.get_context_data", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.get_snmp_engine", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.setup_transport_target", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.bulkCmd")
    @patch("splunk_connect_for_snmp.snmp.manager.getCmd")
    @patch(
        "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.return_collection"
    )
    def test_do_work_get_uses_per_device_max_oid(self, load_profiles, getCmd, bulkCmd):
        poller = Poller.__new__(Poller)
        poller.last_modified = 1609675634
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
        poller.already_loaded_mibs = {}
        poller.profiles_collection = ProfileCollection(poller.profiles)
        poller.profiles_collection.process_profiles()
        getCmd.return_value = [
            (None, 0, 0, "Oid1"),
            (None, 0, 0, "Oid2"),
            (None, 0, 0, "Oid3"),
        ]
        poller.do_work(inventory_record_with_max_oid, profiles=requested_profiles)
        self.assertEqual(poller.process_snmp_data.call_count, 3)
        self.assertEqual(getCmd.call_count, 1)
        self.assertEqual(bulkCmd.call_count, 0)

    @patch("pymongo.MongoClient", MagicMock())
    @patch("mongolock.MongoLock.__init__", MagicMock())
    @patch("mongolock.MongoLock.lock", MagicMock())
    @patch("mongolock.MongoLock.release", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.auth.get_auth", None)
    @patch("splunk_connect_for_snmp.snmp.manager.get_context_data", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.get_snmp_engine", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.setup_transport_target", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.MAX_OID_TO_PROCESS", 70)
    @patch("splunk_connect_for_snmp.snmp.manager.bulkCmd")
    @patch("splunk_connect_for_snmp.snmp.manager.getCmd")
    @patch("splunk_connect_for_snmp.common.collection_manager.ProfilesManager")
    def test_do_work_bulk_falls_back_to_global_max_oid(
        self, load_profiles, getCmd, bulkCmd
    ):
        poller = Poller.__new__(Poller)
        poller.last_modified = 1609675634
        poller.snmp_engine = None
        poller.builder = MagicMock()
        m_process_data = MagicMock()
        m_process_data.return_value = (False, [], {})
        poller.process_snmp_data = m_process_data
        poller.profiles_manager = MagicMock()
        requested_profiles = ["profile1", "profile2"]
        poller.profiles = {
            "profile1": {
                "frequency": 20,
                "varBinds": [["IF-MIB", "ifDescr"], ["IF-MIB", "ifSpeed"]],
            },
            "profile2": {"frequency": 20, "varBinds": [["UDP-MIB", "udpOutDatagrams"]]},
        }
        poller.already_loaded_mibs = {}
        poller.profiles_collection = ProfileCollection(poller.profiles)
        poller.profiles_collection.process_profiles()
        bulkCmd.return_value = [(None, 0, 0, "Oid1")]
        poller.do_work(inventory_record, profiles=requested_profiles)
        self.assertEqual(bulkCmd.call_count, 1)


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
