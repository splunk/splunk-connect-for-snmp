import socket
from unittest import TestCase
from unittest.mock import Mock

from pysnmp.proto import rfc1902
from pysnmp.smi import error

from splunk_connect_for_snmp.snmp.manager import (
    Poller,
    format_trap_varbind_value,
    is_mib_resolved,
)


class TestMibProcessing(TestCase):
    def test_format_trap_varbind_value_ipv4_octets(self):
        octets = rfc1902.OctetString(socket.inet_aton("10.1.1.1"))
        self.assertEqual("10.1.1.1", format_trap_varbind_value(octets))

    def test_format_trap_varbind_value_ipv6_octets(self):
        octets = rfc1902.OctetString(socket.inet_pton(socket.AF_INET6, "2001:db8::1"))
        self.assertEqual("2001:db8::1", format_trap_varbind_value(octets))

    def test_format_trap_varbind_value_keeps_pretty_print(self):
        self.assertEqual("3", format_trap_varbind_value(rfc1902.Integer(3)))

    def test_load_mib(self):
        poller = Poller.__new__(Poller)
        poller.builder = Mock()
        loaded = poller.load_mibs(["a", "b", "c"])
        calls = poller.builder.loadModules.call_args_list

        self.assertEqual({"a", "b", "c"}, loaded)
        self.assertEqual("a", calls[0][0][0])
        self.assertEqual("b", calls[1][0][0])
        self.assertEqual("c", calls[2][0][0])

    def test_load_mib_returns_only_successful(self):
        poller = Poller.__new__(Poller)
        poller.builder = Mock()
        poller.builder.loadModules.side_effect = [
            None,
            error.MibLoadError(),
            None,
        ]
        loaded = poller.load_mibs(["a", "b", "c"])
        self.assertEqual({"a", "c"}, loaded)

    def test_is_mib_known_when_mib_map_is_empty(self):
        poller = Poller.__new__(Poller)
        poller.mib_map = {}
        found, mib = poller.is_mib_known("some ID", "1.2.3.4.5.6", "address")

        self.assertFalse(found)
        self.assertEqual(mib, "")

    def test_is_mib_known(self):
        poller = Poller.__new__(Poller)
        poller.mib_map = {"1.2.3.4.5.6": "test1"}
        found, mib = poller.is_mib_known("some ID", "1.2.3.4.5.6.7", "address")

        self.assertTrue(found)
        self.assertEqual("test1", mib)

    def test_is_mib_known_prefix_limit(self):
        poller = Poller.__new__(Poller)
        poller.mib_map = {"1.2.3.4.5": "test1"}
        found, mib = poller.is_mib_known("some ID", "1.2.3.4.5.6.7", "address")

        self.assertFalse(found)
        self.assertEqual(mib, "")

    def test_is_mib_resolved(self):
        self.assertFalse(is_mib_resolved("RFC1213-MIB::"))
        self.assertFalse(is_mib_resolved("SNMPv2-SMI::enterprises."))
        self.assertFalse(is_mib_resolved("SNMPv2-SMI::mib-2"))
        self.assertTrue(is_mib_resolved("OTHER"))

    def test_exception_during_loading(self):
        poller = Poller.__new__(Poller)
        poller.builder = Mock()
        poller.builder.loadModules.side_effect = error.MibLoadError()
        loaded = poller.load_mibs(["a"])
        self.assertEqual(set(), loaded)

    def test_find_new_mibs_is_found(self):
        poller = Poller.__new__(Poller)
        poller.is_mib_known = Mock()
        poller.is_mib_known.return_value = (True, "SNMPv2-SMI")
        remote_mib = ["SNMPv2-SMI"]
        found = poller.find_new_mibs("1.3.6.1.3.4", remote_mib, "address", "some ID")

        self.assertTrue(found)
        self.assertEqual(remote_mib, ["SNMPv2-SMI"])

    def test_find_new_mibs_add_new(self):
        poller = Poller.__new__(Poller)
        poller.is_mib_known = Mock()
        poller.is_mib_known.return_value = (False, "SNMPv2-SMI")
        remote_mib = ["RFC1213-MIB"]
        found = poller.find_new_mibs("1.3.6.1.3.4", remote_mib, "address", "some ID")

        self.assertEqual(remote_mib, ["RFC1213-MIB", "SNMPv2-SMI"])
        self.assertFalse(found)
