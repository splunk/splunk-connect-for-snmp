from unittest import TestCase
from unittest.mock import Mock

from pysnmp.smi import error

from splunk_connect_for_snmp.snmp.manager import Poller, isMIBResolved


class TestMibProcessing(TestCase):
    def test_load_mib(self):
        poller = Poller.__new__(Poller)
        poller.builder = Mock()
        poller.load_mibs(["a", "b", "c"])
        calls = poller.builder.loadModules.call_args_list

        self.assertEqual("a", calls[0][0][0])
        self.assertEqual("b", calls[1][0][0])
        self.assertEqual("c", calls[2][0][0])

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
        self.assertFalse(isMIBResolved("RFC1213-MIB::"))
        self.assertFalse(isMIBResolved("SNMPv2-SMI::enterprises."))
        self.assertFalse(isMIBResolved("SNMPv2-SMI::mib-2"))
        self.assertTrue(isMIBResolved("OTHER"))

    def test_exception_during_loading(self):
        poller = Poller.__new__(Poller)
        poller.builder = Mock()
        poller.builder.loadModules.side_effect = error.MibLoadError()
        poller.load_mibs(["a"])
