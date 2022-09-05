from unittest import TestCase
from unittest.mock import MagicMock, patch

from splunk_connect_for_snmp.common.inventory_record import InventoryRecord
from splunk_connect_for_snmp.snmp.exceptions import SnmpActionError
from splunk_connect_for_snmp.snmp.manager import Poller

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


class TestDoWork(TestCase):
    @patch("pymongo.MongoClient", MagicMock())
    @patch("mongolock.MongoLock.__init__", MagicMock())
    @patch("mongolock.MongoLock.lock", MagicMock())
    @patch("mongolock.MongoLock.release", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.auth.GetAuth", None)
    @patch("splunk_connect_for_snmp.snmp.manager.get_context_data", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.UdpTransportTarget", MagicMock())
    def test_do_work_no_work_to_do(self):
        poller = Poller.__new__(Poller)
        poller.last_modified = 1609675634
        poller.snmpEngine = None
        poller.profiles_manager = MagicMock()

        varbinds_bulk, varbinds_get = set(), set()
        get_mapping, bulk_mapping = {}, {}

        poller.get_var_binds = MagicMock()
        poller.get_var_binds.return_value = (
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
    @patch("splunk_connect_for_snmp.snmp.auth.GetAuth", None)
    @patch("splunk_connect_for_snmp.snmp.manager.get_context_data", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.UdpTransportTarget", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.bulkCmd")
    @patch("splunk_connect_for_snmp.snmp.manager.getCmd")
    @patch("splunk_connect_for_snmp.common.collection_manager.ProfilesManager")
    def test_do_work_bulk(self, load_profiles, getCmd, bulkCmd):
        poller = Poller.__new__(Poller)
        poller.last_modified = 1609675634
        poller.snmpEngine = None
        poller.builder = MagicMock()
        poller.profiles_manager = MagicMock()
        m_process_data = MagicMock()
        m_process_data.return_value = (False, [], {})
        poller.process_snmp_data = m_process_data
        requested_profiles = ["profile1", "profile2"]
        poller.profiles_manager.return_collection.return_value = {
            "profile1": {
                "frequency": 20,
                "varBinds": [["IF-MIB", "ifDescr"], ["IF-MIB", "ifSpeed"]],
            },
            "profile2": {"frequency": 20, "varBinds": [["UDP-MIB", "udpOutDatagrams"]]},
        }
        bulkCmd.return_value = [(None, 0, 0, "Oid1"), (None, 0, 0, "Oid2")]
        poller.do_work(inventory_record, profiles=requested_profiles)
        self.assertEqual(poller.process_snmp_data.call_count, 2)
        self.assertEqual(getCmd.call_count, 0)
        self.assertEqual(bulkCmd.call_count, 1)

    @patch("pymongo.MongoClient", MagicMock())
    @patch("mongolock.MongoLock.__init__", MagicMock())
    @patch("mongolock.MongoLock.lock", MagicMock())
    @patch("mongolock.MongoLock.release", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.auth.GetAuth", None)
    @patch("splunk_connect_for_snmp.snmp.manager.get_context_data", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.UdpTransportTarget", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.bulkCmd")
    @patch("splunk_connect_for_snmp.snmp.manager.getCmd")
    @patch(
        "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.return_collection"
    )
    def test_do_work_get(self, load_profiles, getCmd, bulkCmd):
        poller = Poller.__new__(Poller)
        poller.last_modified = 1609675634
        poller.snmpEngine = None
        poller.builder = MagicMock()
        poller.process_snmp_data = MagicMock()
        poller.profiles_manager = MagicMock()
        requested_profiles = ["profile1", "profile2"]
        poller.profiles_manager.return_collection.return_value = {
            "profile1": {
                "frequency": 20,
                "varBinds": [["IF-MIB", "ifDescr", 1], ["IF-MIB", "ifSpeed", 2]],
            },
            "profile2": {
                "frequency": 20,
                "varBinds": [["UDP-MIB", "udpOutDatagrams", 1]],
            },
        }
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
    @patch("splunk_connect_for_snmp.snmp.auth.GetAuth", None)
    @patch("splunk_connect_for_snmp.snmp.manager.get_context_data", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.UdpTransportTarget", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.bulkCmd")
    @patch("splunk_connect_for_snmp.snmp.manager.getCmd")
    @patch(
        "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.return_collection"
    )
    def test_do_work_errors(self, load_profiles, getCmd, bulkCmd):
        poller = Poller.__new__(Poller)
        poller.last_modified = 1609675634
        poller.snmpEngine = None
        poller.builder = MagicMock()
        poller.process_snmp_data = MagicMock()
        poller.profiles_manager = MagicMock()
        requested_profiles = ["profile1"]
        poller.profiles_manager.return_collection.return_value = {
            "profile1": {"frequency": 20, "varBinds": [["IF-MIB", "ifDescr", 1]]}
        }
        getCmd.return_value = [(True, True, 2, [])]
        with self.assertRaises(SnmpActionError):
            poller.do_work(inventory_record, profiles=requested_profiles)
        self.assertEqual(poller.process_snmp_data.call_count, 0)
        self.assertEqual(getCmd.call_count, 1)
        self.assertEqual(bulkCmd.call_count, 0)
