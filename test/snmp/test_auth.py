from unittest import TestCase
from unittest.mock import Mock, patch, mock_open

from splunk_connect_for_snmp.common.inventory_record import InventoryRecord
from splunk_connect_for_snmp.snmp.auth import get_secret_value, get_security_engine_id
from splunk_connect_for_snmp.snmp.manager import Poller

mock_secret = """some
value"""


class TestAuth(TestCase):

    @patch('builtins.open', new_callable=mock_open, read_data=mock_secret)
    @patch('os.path.exists')
    def test_get_secret_value_exists(self, m_exists, m_open):
        m_exists.return_value = True
        value = get_secret_value("/location", "key")
        self.assertEqual("somevalue", value)

    @patch('os.path.exists')
    def test_get_secret_value_required(self, m_exists):
        m_exists.return_value = False

        with self.assertRaises(Exception) as e:
            get_secret_value("/location", "my_key", required=True)
        self.assertEqual("Required secret key my_key not found in /location", e.exception.args[0])

    @patch('os.path.exists')
    def test_get_secret_value_default(self, m_exists):
        m_exists.return_value = False

        value = get_secret_value("/location", "key", default="default value")
        self.assertEqual("default value", value)

#    @patch('pysnmp.hlapi.asyncore.sync.compat.cmdgen.getCmd')

#    @patch('pysnmp.hlapi.asyncore.sync.cmdgen.getCmd')
#     @patch('pysnmp.hlapi.getCmd')
#     def test_get_security_engine_id(self, m_get_cmd):
#         ir = InventoryRecord.from_dict({
#             "address": "192.168.0.1",
#             "port": "34",
#             "version": "2c",
#             "community": "public",
#             "secret": "secret",
#             "securityEngine": "ENGINE",
#             "walk_interval": 1850,
#             "profiles": "",
#             "SmartProfiles": True,
#             "delete": False,
#         })
#
#         snmpEngine = Mock()
#         logger = Mock()
#
#         m_get_cmd.side_effect = [(None, None, None, None)]
#         m_get_cmd.return_value = (None, None, None, None)
#
#         get_security_engine_id(logger, ir, snmpEngine)
#
#         calls = snmpEngine.observer.registerObserver.call_args_list
#
#         m_get_cmd.assert_called()
#
#         self.assertTrue(True)

