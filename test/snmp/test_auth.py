from unittest import TestCase
from unittest.mock import Mock, patch, mock_open

from pysnmp.entity.config import usmHMAC128SHA224AuthProtocol, usmAesBlumenthalCfb192Protocol

from splunk_connect_for_snmp.common.inventory_record import InventoryRecord
from splunk_connect_for_snmp.snmp.auth import get_secret_value, getAuthV3, getAuthV2c, \
    getAuthV1, GetAuth

mock_value = """some
value"""

ir = InventoryRecord.from_dict({
    "address": "192.168.0.1",
    "port": "34",
    "version": "2c",
    "community": "public",
    "secret": "secret_ir",
    "securityEngine": "ENGINE",
    "walk_interval": 1850,
    "profiles": "",
    "SmartProfiles": True,
    "delete": False,
})


class TestAuth(TestCase):

    @patch('builtins.open', new_callable=mock_open, read_data=mock_value)
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

    @patch('os.path.exists')
    @patch('splunk_connect_for_snmp.snmp.auth.get_secret_value')
    def test_getAuthV3(self, m_get_secret_value, m_exists):
        m_exists.return_value = True
        m_get_secret_value.side_effect = ["secret1", "secret2", "secret3", "SHA224", "AES192BLMT", "1", "2"]
        logger = Mock()
        snmpEngine = Mock()

        result = getAuthV3(logger, ir, snmpEngine)

        self.assertEqual("secret1", result.userName)
        self.assertEqual("secret2", result.authKey)
        self.assertEqual("secret3", result.privKey)
        self.assertEqual(usmHMAC128SHA224AuthProtocol, result.authProtocol)
        self.assertEqual(usmAesBlumenthalCfb192Protocol, result.privProtocol)
        self.assertEqual("ENGINE", result.securityEngineId)
        self.assertEqual("secret1", result.securityName)
        self.assertEqual(1, result.authKeyType)
        self.assertEqual(2, result.privKeyType)

    @patch('os.path.exists')
    @patch('splunk_connect_for_snmp.snmp.auth.get_secret_value')
    def test_getAuthV3_exception(self, m_get_secret_value, m_exists):
        m_exists.return_value = False
        m_get_secret_value.side_effect = ["secret1", "secret2", "secret3", "SHA224", "AES192BLMT", "1", "2"]
        logger = Mock()

        snmpEngine = Mock()

        with self.assertRaises(Exception) as e:
            result = getAuthV3(logger, ir, snmpEngine)
        self.assertEqual("invalid username from secret secret_ir", e.exception.args[0])

    def test_getAuthV2c(self):
        result = getAuthV2c(ir)
        self.assertEqual("public", result.communityName)
        self.assertEqual(1, result.mpModel)

    def test_getAuthV1(self):
        result = getAuthV1(ir)
        self.assertEqual("public", result.communityName)
        self.assertEqual(0, result.mpModel)

    # version 1 is not supported in
    # @patch('splunk_connect_for_snmp.snmp.auth.getAuthV1')
    # def test_getAuth1(self, m_get_auth):
    #     ir.version = "1"
    #     result = GetAuth(Mock(), ir, Mock())
    #     m_get_auth.assert_called()

    @patch('splunk_connect_for_snmp.snmp.auth.getAuthV2c')
    def test_getAuth2(self, m_get_auth):
        ir.version = "2c"
        result = GetAuth(Mock(), ir, Mock())
        m_get_auth.assert_called()

    @patch('splunk_connect_for_snmp.snmp.auth.getAuthV3')
    def test_getAuth3(self, m_get_auth):
        ir.version = "3"
        result = GetAuth(Mock(), ir, Mock())
        m_get_auth.assert_called()
