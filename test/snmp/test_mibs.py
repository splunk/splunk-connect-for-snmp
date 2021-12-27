from unittest import TestCase
from unittest.mock import Mock

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
        found, mib = poller.isMIBKnown("some ID", "1.2.3.4.5.6")

        self.assertFalse(found)
        self.assertIsNone(mib)

    def test_is_mib_known(self):
        poller = Poller.__new__(Poller)
        poller.mib_map = {"1.2.3.4.5.6": "test1"}
        found, mib = poller.isMIBKnown("some ID", "1.2.3.4.5.6.7")

        self.assertTrue(found)
        self.assertEqual("test1", mib)

    def test_is_mib_known_prefix_limit(self):
        poller = Poller.__new__(Poller)
        poller.mib_map = {"1.2.3.4.5": "test1"}
        found, mib = poller.isMIBKnown("some ID", "1.2.3.4.5.6.7")

        self.assertFalse(found)
        self.assertIsNone(mib)

    def test_is_mib_resolved(self):
        self.assertFalse(isMIBResolved("RFC1213-MIB::"))
        self.assertFalse(isMIBResolved("SNMPv2-SMI::enterprises."))
        self.assertFalse(isMIBResolved("SNMPv2-SMI::mib-2"))
        self.assertTrue(isMIBResolved("OTHER"))
