from unittest import TestCase
from unittest.mock import MagicMock, Mock, mock_open, patch

from pysnmp.entity.config import (
    usmAesBlumenthalCfb192Protocol,
    usmHMAC128SHA224AuthProtocol,
    usmNoAuthProtocol,
    usmNoPrivProtocol,
)
from pysnmp.proto.rfc1902 import OctetString

from splunk_connect_for_snmp.common.inventory_record import InventoryRecord
from splunk_connect_for_snmp.snmp.auth import (
    fetch_security_engine_id,
    get_auth,
    get_auth_v1,
    get_auth_v2c,
    get_auth_v3,
    get_secret_value,
    get_security_engine_id,
    setup_transport_target,
)
from splunk_connect_for_snmp.snmp.exceptions import SnmpActionError

mock_value = """some
value"""

ir = InventoryRecord(
    **{
        "address": "192.168.0.1",
        "port": "34",
        "version": "2c",
        "community": "public",
        "secret": "secret_ir",
        "securityEngine": "80003a8c04",
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
        ir2 = InventoryRecord(
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
        ir2 = InventoryRecord(
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
        result = fetch_security_engine_id(
            {"securityEngineId": "some_value"}, None, "127.0.0.1"
        )
        self.assertEqual(result, "some_value")

    def test_fetch_security_engine_id_missing(self):
        with self.assertRaises(SnmpActionError) as e:
            fetch_security_engine_id({}, "Some error", "127.0.0.1")
        self.assertEqual(
            "Can't discover peer EngineID for device 127.0.0.1, errorIndication: Some error",
            e.exception.args[0],
        )

    @patch("os.path.exists")
    @patch("splunk_connect_for_snmp.snmp.auth.get_secret_value")
    def test_get_auth_v3(self, m_get_secret_value, m_exists):
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

        result = get_auth_v3(logger, ir, snmpEngine)
        security_engine_result = OctetString(hexValue="80003a8c04")
        self.assertEqual("secret1", result.userName)
        self.assertEqual("secret2", result.authKey)
        self.assertEqual("secret3", result.privKey)
        self.assertEqual("authPriv", result.securityLevel)
        self.assertEqual(usmHMAC128SHA224AuthProtocol, result.authProtocol)
        self.assertEqual(usmAesBlumenthalCfb192Protocol, result.privProtocol)
        self.assertEqual(security_engine_result._value, result.securityEngineId._value)
        self.assertEqual("secret1", result.securityName)
        self.assertEqual(1, result.authKeyType)
        self.assertEqual(2, result.privKeyType)

    @patch("os.path.exists")
    @patch("splunk_connect_for_snmp.snmp.auth.get_secret_value")
    @patch("splunk_connect_for_snmp.snmp.auth.get_security_engine_id")
    def test_get_auth_v3_security_engine_not_str(
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

        ir2 = InventoryRecord(
            **{
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

        result = get_auth_v3(logger, ir2, snmpEngine)

        m_get_security_engine_id.assert_called()

        self.assertEqual("secret1", result.userName)
        self.assertEqual("secret2", result.authKey)
        self.assertEqual("secret3", result.privKey)
        self.assertEqual("authPriv", result.securityLevel)
        self.assertEqual(usmHMAC128SHA224AuthProtocol, result.authProtocol)
        self.assertEqual(usmAesBlumenthalCfb192Protocol, result.privProtocol)
        self.assertEqual("ENGINE123", result.securityEngineId)
        self.assertEqual("secret1", result.securityName)
        self.assertEqual(1, result.authKeyType)
        self.assertEqual(2, result.privKeyType)

    @patch("os.path.exists")
    @patch("splunk_connect_for_snmp.snmp.auth.get_secret_value")
    def test_get_auth_v3_exception(self, m_get_secret_value, m_exists):
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
            get_auth_v3(logger, ir, snmpEngine)
        self.assertEqual("invalid username from secret secret_ir", e.exception.args[0])

    @patch("os.path.exists")
    @patch("splunk_connect_for_snmp.snmp.auth.get_secret_value")
    def test_get_auth_v3_noauthnopriv(self, m_get_secret_value, m_exists):
        m_exists.return_value = True
        m_get_secret_value.side_effect = [
            "secret1",
            "",
            "",
            "SHA224",
            "AES192BLMT",
            "1",
            "2",
        ]
        logger = Mock()
        snmpEngine = Mock()

        result = get_auth_v3(logger, ir, snmpEngine)
        security_engine_result = OctetString(hexValue="80003a8c04")
        self.assertEqual("secret1", result.userName)
        self.assertIsNone(result.authKey)
        self.assertIsNone(result.privKey)
        self.assertEqual("noAuthNoPriv", result.securityLevel)
        self.assertEqual(usmNoAuthProtocol, result.authProtocol)
        self.assertEqual(usmNoPrivProtocol, result.privProtocol)
        self.assertEqual(security_engine_result._value, result.securityEngineId._value)
        self.assertEqual("secret1", result.securityName)
        self.assertEqual(1, result.authKeyType)
        self.assertEqual(2, result.privKeyType)

    @patch("os.path.exists")
    @patch("splunk_connect_for_snmp.snmp.auth.get_secret_value")
    def test_get_auth_v3_authnopriv(self, m_get_secret_value, m_exists):
        m_exists.return_value = True
        m_get_secret_value.side_effect = [
            "secret1",
            "secret2",
            "",
            "SHA224",
            "AES192BLMT",
            "1",
            "2",
        ]
        logger = Mock()
        snmpEngine = Mock()

        result = get_auth_v3(logger, ir, snmpEngine)
        security_engine_result = OctetString(hexValue="80003a8c04")
        self.assertEqual("secret1", result.userName)
        self.assertEqual("secret2", result.authKey)
        self.assertIsNone(result.privKey)
        self.assertEqual("authNoPriv", result.securityLevel)
        self.assertEqual(usmHMAC128SHA224AuthProtocol, result.authProtocol)
        self.assertEqual(usmNoPrivProtocol, result.privProtocol)
        self.assertEqual(security_engine_result._value, result.securityEngineId._value)
        self.assertEqual("secret1", result.securityName)
        self.assertEqual(1, result.authKeyType)
        self.assertEqual(2, result.privKeyType)

    def test_get_auth_v2c(self):
        result = get_auth_v2c(ir)
        self.assertEqual("public", result.communityName)
        self.assertEqual(1, result.mpModel)

    def test_get_auth_v1(self):
        result = get_auth_v1(ir)
        self.assertEqual("public", result.communityName)
        self.assertEqual(0, result.mpModel)

    @patch("splunk_connect_for_snmp.snmp.auth.get_auth_v1")
    def test_get_auth_1(self, m_get_auth):
        ir.version = "1"
        get_auth(Mock(), ir, Mock())
        m_get_auth.assert_called()

    @patch("splunk_connect_for_snmp.snmp.auth.get_auth_v2c")
    def test_get_auth_2c(self, m_get_auth):
        ir.version = "2c"
        get_auth(Mock(), ir, Mock())
        m_get_auth.assert_called()

    @patch("splunk_connect_for_snmp.snmp.auth.get_auth_v3")
    def test_get_auth_3(self, m_get_auth):
        ir.version = "3"
        get_auth(Mock(), ir, Mock())
        m_get_auth.assert_called()

    @patch("splunk_connect_for_snmp.snmp.auth.Udp6TransportTarget")
    @patch("splunk_connect_for_snmp.snmp.auth.UdpTransportTarget")
    def test_setup_transport_target_ipv4(
        self, m_setup_udp_transport_target, m_setup_udp6_transport_target
    ):
        ir.address = "127.0.0.1"
        ir.port = 161
        m_setup_udp_transport_target.return_value = "UDP4"
        m_setup_udp6_transport_target.return_value = "UDP6"
        transport = setup_transport_target(ir)
        self.assertEqual("UDP4", transport)

    @patch("splunk_connect_for_snmp.snmp.auth.IPv6_ENABLED")
    @patch("splunk_connect_for_snmp.snmp.auth.Udp6TransportTarget")
    @patch("splunk_connect_for_snmp.snmp.auth.UdpTransportTarget")
    def test_setup_transport_target_ipv6(
        self, m_setup_udp_transport_target, m_setup_udp6_transport_target, ipv6_enabled
    ):
        ipv6_enabled.return_value = True
        ir.address = "2001:0db8:ac10:fe01::0001"
        ir.port = 161
        m_setup_udp_transport_target.return_value = "UDP4"
        m_setup_udp6_transport_target.return_value = "UDP6"
        transport = setup_transport_target(ir)
        self.assertEqual("UDP6", transport)
