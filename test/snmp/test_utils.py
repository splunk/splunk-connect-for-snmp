from unittest import TestCase, mock
from unittest.mock import Mock

from splunk_connect_for_snmp.snmp.context import get_context_data
from splunk_connect_for_snmp.snmp.exceptions import SnmpActionError
from splunk_connect_for_snmp.snmp.manager import (
    _any_failure_happened,
    extract_index_number,
    fill_empty_value,
    get_inventory,
    is_increasing_oids_ignored,
    map_metric_type,
    return_address_and_port,
)


class TestUtils(TestCase):
    def test_get_inventory_none(self):
        inventory = Mock()
        inventory.find_one.return_value = None
        with self.assertRaises(ValueError):
            get_inventory(inventory, "192.168.0.1")

    def test_get_inventory(self):
        inventory = Mock()
        inventory.find_one.return_value = {
            "address": "192.168.0.1",
            "port": 162,
            "version": "2c",
            "community": "public",
            "secret": "some_secret",
            "securityEngine": "some_engine",
            "walk_interval": 1820,
            "profiles": "profile1;profile2",
            "SmartProfiles": True,
            "delete": False,
        }
        ir = get_inventory(inventory, "192.168.0.1")

        self.assertEqual("192.168.0.1", ir.address)
        self.assertEqual(162, ir.port)
        self.assertEqual("2c", ir.version)
        self.assertEqual("public", ir.community)
        self.assertEqual("some_secret", ir.secret)
        self.assertEqual("some_engine", ir.securityEngine)
        self.assertEqual(1820, ir.walk_interval)
        self.assertEqual(["profile1", "profile2"], ir.profiles)
        self.assertEqual(True, ir.SmartProfiles)
        self.assertEqual(False, ir.delete)

    def test_any_failure_happened_error_indication(self):
        error_indication = "Error indication"
        error_status = None
        error_index = 1
        var_binds = []
        address = "192.168.0.1"
        walk = False
        with self.assertRaises(SnmpActionError) as sae:
            _any_failure_happened(
                error_indication, error_status, error_index, var_binds, address, walk
            )
        self.assertEqual(
            "An error of SNMP isWalk=False for a host 192.168.0.1 occurred: Error indication",
            sae.exception.args[0],
        )

    def test_any_failure_happened_error_status(self):
        error_indication = None
        error_status = Mock()
        error_status.prettyPrint.return_value = "Some error status"
        error_index = 1
        var_binds = [("Some varbind", "asd")]
        address = "192.168.0.1"
        walk = False
        with self.assertRaises(SnmpActionError) as sae:
            _any_failure_happened(
                error_indication, error_status, error_index, var_binds, address, walk
            )
        self.assertEqual(
            "An error of SNMP isWalk=False for a host 192.168.0.1 occurred: Some error status at Some "
            "varbind",
            sae.exception.args[0],
        )

    def test_any_failure_happened_no_error(self):
        error_indication = None
        error_status = None
        error_index = None
        var_binds = []
        address = "192.168.0.1"
        walk = False
        result = _any_failure_happened(
            error_indication, error_status, error_index, var_binds, address, walk
        )
        self.assertFalse(result)

    def test_map_metric_type(self):
        self.assertEqual("cc", map_metric_type("Counter32", 2))
        self.assertEqual("cc", map_metric_type("Counter64", 2))
        self.assertEqual("cc", map_metric_type("TimeTicks", 2))

        self.assertEqual("g", map_metric_type("Gauge32", 2))
        self.assertEqual("g", map_metric_type("Gauge64", 2))
        self.assertEqual("g", map_metric_type("Integer", 2))
        self.assertEqual("g", map_metric_type("Integer32", 2))
        self.assertEqual("g", map_metric_type("Unsigned32", 2))
        self.assertEqual("g", map_metric_type("Unsigned64", 2))

        self.assertEqual("r", map_metric_type("ObjectIdentifier", 2))
        self.assertEqual("r", map_metric_type("ObjectIdentity", 2))

        self.assertEqual("f", map_metric_type("Other", 2))
        self.assertEqual("te", map_metric_type("Counter32", "asd"))

    def test_fill_empty_value(self):
        self.assertEqual(1, fill_empty_value(1, None, "192.168.0.1"))
        self.assertEqual(1, fill_empty_value(1, "", "192.168.0.1"))
        self.assertEqual("asd", fill_empty_value(b"asd", None, "192.168.0.1"))
        self.assertEqual("asd", fill_empty_value(b"asd", "", "192.168.0.1"))
        self.assertEqual("asd", fill_empty_value(1, "asd", "192.168.0.1"))
        self.assertEqual(
            "sc4snmp:unconvertable",
            fill_empty_value(b"\xde\xad\xbe\xef", "", "192.168.0.1"),
        )

    def test_extract_index_number(self):

        index = Mock()
        index._value = (3, 4)

        index2 = Mock()
        index2._value = 5

        self.assertEqual(0, extract_index_number(None))
        self.assertEqual(3, extract_index_number((index, None)))
        self.assertEqual(5, extract_index_number((index2, None)))

    def test_get_context_data(self):
        result = get_context_data()

        self.assertIsNone(result.contextEngineId)
        self.assertEqual("", result.contextName)

    def test_return_address_and_port(self):
        self.assertEqual(return_address_and_port("127.0.0.1"), ("127.0.0.1", 161))
        self.assertEqual(return_address_and_port("168.99.9.9"), ("168.99.9.9", 161))
        self.assertEqual(return_address_and_port("168.99.9.9:162"), ("168.99.9.9", 162))

    @mock.patch(
        "splunk_connect_for_snmp.snmp.manager.HOSTS_TO_IGNORE_NOT_INCREASING_OIDS",
        ["127.0.0.1"],
    )
    def test_is_increasing_oids_ignored_only_host(self):
        self.assertTrue(is_increasing_oids_ignored("127.0.0.1", "161"))
        self.assertFalse(is_increasing_oids_ignored("127.0.0.2", "161"))
        self.assertTrue(is_increasing_oids_ignored("127.0.0.1", "162"))

    @mock.patch(
        "splunk_connect_for_snmp.snmp.manager.HOSTS_TO_IGNORE_NOT_INCREASING_OIDS",
        ["127.0.0.1:162"],
    )
    def test_is_increasing_oids_ignored(self):
        self.assertFalse(is_increasing_oids_ignored("127.0.0.1", "161"))
        self.assertFalse(is_increasing_oids_ignored("127.0.0.2", "161"))
        self.assertTrue(is_increasing_oids_ignored("127.0.0.1", "162"))

    @mock.patch(
        "splunk_connect_for_snmp.snmp.manager.HOSTS_TO_IGNORE_NOT_INCREASING_OIDS", []
    )
    def test_is_increasing_oids_ignored_empty(self):
        self.assertFalse(is_increasing_oids_ignored("127.0.0.1", "161"))
        self.assertFalse(is_increasing_oids_ignored("127.0.0.2", "161"))
        self.assertFalse(is_increasing_oids_ignored("127.0.0.1", "162"))
