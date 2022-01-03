from unittest import TestCase
from unittest.mock import patch, MagicMock

from splunk_connect_for_snmp.common.inventory_record import InventoryRecord
from splunk_connect_for_snmp.snmp.exceptions import SnmpActionError
from splunk_connect_for_snmp.snmp.manager import Poller


class TestDoWork(TestCase):

    inventory_record = InventoryRecord.from_dict({
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
    })


    @patch('pymongo.MongoClient')
    @patch('mongolock.MongoLock.__init__')
    @patch('mongolock.MongoLock.lock')
    @patch('mongolock.MongoLock.release')
    @patch('splunk_connect_for_snmp.snmp.manager.get_inventory')
    @patch('splunk_connect_for_snmp.snmp.auth.GetAuth', None)
    @patch('splunk_connect_for_snmp.snmp.manager.get_context_data', MagicMock())
    @patch('splunk_connect_for_snmp.snmp.manager.UdpTransportTarget', MagicMock())
    def test_do_work_no_work_to_do(self, m_get_inventory, m_release, m_lock, m_mongo_lock, m_mongo_client):
        poller = Poller.__new__(Poller)
        poller.last_modified = 1609675634
        poller.snmpEngine = None

        varbinds_bulk, varbinds_get = set(), set()
        get_mapping, bulk_mapping = {}, {}

        poller.get_var_binds = MagicMock()
        poller.get_var_binds.return_value = varbinds_get, get_mapping, varbinds_bulk, bulk_mapping
        m_get_inventory.return_value = TestDoWork.inventory_record
        result = poller.do_work("192.168.0.1")
        self.assertEqual(result, {})

    @patch('pymongo.MongoClient')
    @patch('mongolock.MongoLock.__init__')
    @patch('mongolock.MongoLock.lock')
    @patch('mongolock.MongoLock.release')
    @patch('splunk_connect_for_snmp.snmp.manager.get_inventory')
    @patch('splunk_connect_for_snmp.snmp.auth.GetAuth', None)
    @patch('splunk_connect_for_snmp.snmp.manager.get_context_data', MagicMock())
    @patch('splunk_connect_for_snmp.snmp.manager.UdpTransportTarget', MagicMock())
    @patch('splunk_connect_for_snmp.snmp.manager.bulkCmd')
    @patch('splunk_connect_for_snmp.snmp.manager.getCmd')
    @patch('splunk_connect_for_snmp.snmp.manager.load_profiles')
    def test_do_work_bulk(self, load_profiles, getCmd, bulkCmd, m_get_inventory, m_release, m_lock, m_mongo_lock, m_mongo_client):
        poller = Poller.__new__(Poller)
        poller.last_modified = 1609675634
        poller.snmpEngine = None
        poller.builder = MagicMock()
        poller.process_snmp_data = MagicMock()
        requested_profiles = ["profile1", "profile2"]
        load_profiles.return_value = {"profile1": {"frequency": 20,
                                        "varBinds": [["IF-MIB", "ifDescr"], ["IF-MIB", "ifSpeed"]]},
                           "profile2": {"frequency": 20,
                                        "varBinds": [["UDP-MIB", "udpOutDatagrams"]]}}
        m_get_inventory.return_value = TestDoWork.inventory_record
        bulkCmd.return_value = [(None, 0, 0, "Oid1"), (None, 0, 0, "Oid2")]
        poller.do_work("192.168.0.1", profiles=requested_profiles)
        self.assertEqual(poller.process_snmp_data.call_count, 2)
        self.assertEqual(getCmd.call_count, 0)
        self.assertEqual(bulkCmd.call_count, 1)

    @patch('pymongo.MongoClient')
    @patch('mongolock.MongoLock.__init__')
    @patch('mongolock.MongoLock.lock')
    @patch('mongolock.MongoLock.release')
    @patch('splunk_connect_for_snmp.snmp.manager.get_inventory')
    @patch('splunk_connect_for_snmp.snmp.auth.GetAuth', None)
    @patch('splunk_connect_for_snmp.snmp.manager.get_context_data', MagicMock())
    @patch('splunk_connect_for_snmp.snmp.manager.UdpTransportTarget', MagicMock())
    @patch('splunk_connect_for_snmp.snmp.manager.bulkCmd')
    @patch('splunk_connect_for_snmp.snmp.manager.getCmd')
    @patch('splunk_connect_for_snmp.snmp.manager.load_profiles')
    def test_do_work_get(self, load_profiles, getCmd, bulkCmd, m_get_inventory, m_release, m_lock, m_mongo_lock, m_mongo_client):
        poller = Poller.__new__(Poller)
        poller.last_modified = 1609675634
        poller.snmpEngine = None
        poller.builder = MagicMock()
        poller.process_snmp_data = MagicMock()
        requested_profiles = ["profile1", "profile2"]
        load_profiles.return_value = {"profile1": {"frequency": 20,
                                        "varBinds": [["IF-MIB", "ifDescr", 1], ["IF-MIB", "ifSpeed", 2]]},
                           "profile2": {"frequency": 20,
                                        "varBinds": [["UDP-MIB", "udpOutDatagrams", 1]]}}
        m_get_inventory.return_value = TestDoWork.inventory_record
        getCmd.return_value = [(None, 0, 0, "Oid1"), (None, 0, 0, "Oid2"), (None, 0, 0, "Oid3")]
        poller.do_work("192.168.0.1", profiles=requested_profiles)
        self.assertEqual(poller.process_snmp_data.call_count, 3)
        self.assertEqual(getCmd.call_count, 1)
        self.assertEqual(bulkCmd.call_count, 0)

    @patch('pymongo.MongoClient')
    @patch('mongolock.MongoLock.__init__')
    @patch('mongolock.MongoLock.lock')
    @patch('mongolock.MongoLock.release')
    @patch('splunk_connect_for_snmp.snmp.manager.get_inventory')
    @patch('splunk_connect_for_snmp.snmp.auth.GetAuth', None)
    @patch('splunk_connect_for_snmp.snmp.manager.get_context_data', MagicMock())
    @patch('splunk_connect_for_snmp.snmp.manager.UdpTransportTarget', MagicMock())
    @patch('splunk_connect_for_snmp.snmp.manager.bulkCmd')
    @patch('splunk_connect_for_snmp.snmp.manager.getCmd')
    @patch('splunk_connect_for_snmp.snmp.manager.load_profiles')
    def test_do_work_errors(self, load_profiles, getCmd, bulkCmd, m_get_inventory, m_release, m_lock, m_mongo_lock, m_mongo_client):
        poller = Poller.__new__(Poller)
        poller.last_modified = 1609675634
        poller.snmpEngine = None
        poller.builder = MagicMock()
        poller.process_snmp_data = MagicMock()
        requested_profiles = ["profile1"]
        load_profiles.return_value = {"profile1": {"frequency": 20,
                                        "varBinds": [["IF-MIB", "ifDescr", 1]]}}
        m_get_inventory.return_value = TestDoWork.inventory_record
        getCmd.return_value = [(True, True, 2, [])]
        with self.assertRaises(SnmpActionError):
            poller.do_work("192.168.0.1", profiles=requested_profiles)
        self.assertEqual(poller.process_snmp_data.call_count, 0)
        self.assertEqual(getCmd.call_count, 1)
        self.assertEqual(bulkCmd.call_count, 0)
