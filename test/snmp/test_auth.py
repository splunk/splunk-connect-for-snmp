from unittest import TestCase
from unittest.mock import Mock, mock_open, patch

from pysnmp.entity.config import (
    usmAesBlumenthalCfb192Protocol,
    usmHMAC128SHA224AuthProtocol,
)
from pysnmp.entity.engine import SnmpEngine

from splunk_connect_for_snmp.common.inventory_record import InventoryRecord
from splunk_connect_for_snmp.snmp.auth import (
    GetAuth,
    fetch_security_engine_id,
    get_secret_value,
    get_security_engine_id,
    getAuthV1,
    getAuthV2c,
    getAuthV3,
)
from splunk_connect_for_snmp.snmp.exceptions import SnmpActionError

mock_value = """some
value"""

ir = InventoryRecord.from_dict(
    {
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
    }
)


class TestAuth(TestCase):
    @patch("builtins.open", new_callable=mock_open, read_data=mock_value)
    @patch("os.path.exists")
    def test_get_secret_value_exists(self, m_exists, m_open):
        m_exists.return_value = True
        value = get_secret_value("/location", "key")
        self.assertEqual("somevalue", value)

    @patch("os.path.exists")
    def test_get_secret_value_required(self, m_exists):
        m_exists.return_value = False

        with self.assertRaises(Exception) as e:
            get_secret_value("/location", "my_key", required=True)
        self.assertEqual(
            "Required secret key my_key not found in /location", e.exception.args[0]
        )

    @patch("os.path.exists")
    def test_get_secret_value_default(self, m_exists):
        m_exists.return_value = False

        value = get_secret_value("/location", "key", default="default value")
        self.assertEqual("default value", value)

    @patch("splunk_connect_for_snmp.snmp.auth.getCmd")
    @patch("splunk_connect_for_snmp.snmp.auth.fetch_security_engine_id")
    def test_get_security_engine_id_not_present(self, m_fetch, m_get_cmd):
        ir2 = InventoryRecord.from_dict(
            {
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

        snmpEngine = Mock()
        logger = Mock()

        m_get_cmd.return_value = iter(
            [(None, 0, 0, "Oid1"), (None, 0, 0, "Oid2"), (None, 0, 0, "Oid3")]
        )
        m_fetch.side_effect = Exception("boom")

        with self.assertRaises(Exception) as e:
            get_security_engine_id(logger, ir2, snmpEngine)
        self.assertEqual("boom", e.exception.args[0])

        calls = snmpEngine.observer.registerObserver.call_args_list

        self.assertEqual("rfc3412.prepareDataElements:internal", calls[0].args[1])

        m_get_cmd.assert_called()

    @patch("splunk_connect_for_snmp.snmp.auth.getCmd")
    @patch("splunk_connect_for_snmp.snmp.auth.fetch_security_engine_id")
    def test_get_security_engine_id(self, m_fetch, m_get_cmd):
        ir2 = InventoryRecord.from_dict(
            {
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

        snmpEngine = Mock()
        logger = Mock()
        m_fetch.return_value = "My test value"

        m_get_cmd.return_value = iter(
            [(None, 0, 0, "Oid1"), (None, 0, 0, "Oid2"), (None, 0, 0, "Oid3")]
        )

        result = get_security_engine_id(logger, ir2, snmpEngine)

        calls = snmpEngine.observer.registerObserver.call_args_list

        self.assertEqual("rfc3412.prepareDataElements:internal", calls[0].args[1])

        m_get_cmd.assert_called()
        self.assertEqual(result, "My test value")

    def test_fetch_security_engine_id(self):
        result = fetch_security_engine_id({"securityEngineId": "some_value"}, None)
        self.assertEqual(result, "some_value")

    def test_fetch_security_engine_id_missing(self):
        with self.assertRaises(SnmpActionError) as e:
            fetch_security_engine_id({}, "Some error")
        self.assertEqual(
            "Can't discover peer EngineID, errorIndication: Some error",
            e.exception.args[0],
        )

    @patch("os.path.exists")
    @patch("splunk_connect_for_snmp.snmp.auth.get_secret_value")
    def test_getAuthV3(self, m_get_secret_value, m_exists):
        m_exists.return_value = True
        m_get_secret_value.side_effect = [
            "secret1",
            "secret2",
            "secret3",
            "SHA224",
            "AES192BLMT",
            "1",
            "2",
        ]
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

    @patch("os.path.exists")
    @patch("splunk_connect_for_snmp.snmp.auth.get_secret_value")
    @patch("splunk_connect_for_snmp.snmp.auth.get_security_engine_id")
    def test_getAuthV3_security_engine_not_str(
        self, m_get_security_engine_id, m_get_secret_value, m_exists
    ):
        m_exists.return_value = True
        m_get_secret_value.side_effect = [
            "secret1",
            "secret2",
            "secret3",
            "SHA224",
            "AES192BLMT",
            "1",
            "2",
        ]
        m_get_security_engine_id.return_value = "ENGINE123"
        logger = Mock()
        snmpEngine = Mock()

        ir2 = InventoryRecord.from_dict(
            {
                "address": "192.168.0.1",
                "port": "34",
                "version": "2c",
                "community": "public",
                "secret": "secret_ir",
                "securityEngine": 123,
                "walk_interval": 1850,
                "profiles": "",
                "SmartProfiles": True,
                "delete": False,
            }
        )

        result = getAuthV3(logger, ir2, snmpEngine)

        m_get_security_engine_id.assert_called()

        self.assertEqual("secret1", result.userName)
        self.assertEqual("secret2", result.authKey)
        self.assertEqual("secret3", result.privKey)
        self.assertEqual(usmHMAC128SHA224AuthProtocol, result.authProtocol)
        self.assertEqual(usmAesBlumenthalCfb192Protocol, result.privProtocol)
        self.assertEqual("ENGINE123", result.securityEngineId)
        self.assertEqual("secret1", result.securityName)
        self.assertEqual(1, result.authKeyType)
        self.assertEqual(2, result.privKeyType)

    @patch("os.path.exists")
    @patch("splunk_connect_for_snmp.snmp.auth.get_secret_value")
    def test_getAuthV3_exception(self, m_get_secret_value, m_exists):
        m_exists.return_value = False
        m_get_secret_value.side_effect = [
            "secret1",
            "secret2",
            "secret3",
            "SHA224",
            "AES192BLMT",
            "1",
            "2",
        ]
        logger = Mock()

        snmpEngine = Mock()

        with self.assertRaises(Exception) as e:
            getAuthV3(logger, ir, snmpEngine)
        self.assertEqual("invalid username from secret secret_ir", e.exception.args[0])

    def test_getAuthV2c(self):
        result = getAuthV2c(ir)
        self.assertEqual("public", result.communityName)
        self.assertEqual(1, result.mpModel)

    def test_getAuthV1(self):
        result = getAuthV1(ir)
        self.assertEqual("public", result.communityName)
        self.assertEqual(0, result.mpModel)

    @patch("splunk_connect_for_snmp.snmp.auth.getAuthV1")
    def test_getAuth1(self, m_get_auth):
        ir.version = "1"
        GetAuth(Mock(), ir, Mock())
        m_get_auth.assert_called()

    @patch("splunk_connect_for_snmp.snmp.auth.getAuthV2c")
    def test_getAuth2(self, m_get_auth):
        ir.version = "2c"
        GetAuth(Mock(), ir, Mock())
        m_get_auth.assert_called()

    @patch("splunk_connect_for_snmp.snmp.auth.getAuthV3")
    def test_getAuth3(self, m_get_auth):
        ir.version = "3"
        GetAuth(Mock(), ir, Mock())
        m_get_auth.assert_called()
