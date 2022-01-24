from unittest import TestCase
from unittest.mock import patch

from pysnmp.proto.errind import EmptyResponse

from splunk_connect_for_snmp.snmp.exceptions import SnmpActionError
from splunk_connect_for_snmp.snmp.manager import _any_failure_happened


class TestAnyFailureHappened(TestCase):
    def test__any_failure_happened_default(self):
        error_indication = EmptyResponse("Empty SNMP response message")
        with self.assertRaises(SnmpActionError) as ctx:
            _any_failure_happened(error_indication, 0, 0, [], "127.0.0.1", True)
        self.assertEqual(
            "An error of SNMP isWalk=True for a host 127.0.0.1 occurred: Empty SNMP response message",
            str(ctx.exception),
        )

    @patch("splunk_connect_for_snmp.snmp.manager.IGNORE_EMPTY_VARBINDS", False)
    def test__any_failure_happened_ignore_false(self):
        error_indication = EmptyResponse("Empty SNMP response message")
        with self.assertRaises(SnmpActionError) as ctx:
            _any_failure_happened(error_indication, 0, 0, [], "127.0.0.1", True)
        self.assertEqual(
            "An error of SNMP isWalk=True for a host 127.0.0.1 occurred: Empty SNMP response message",
            str(ctx.exception),
        )

    @patch("splunk_connect_for_snmp.snmp.manager.IGNORE_EMPTY_VARBINDS", True)
    def test__any_failure_happened_ignore_true(self):
        error_indication = EmptyResponse("Empty SNMP response message")
        self.assertEqual(
            _any_failure_happened(error_indication, 0, 0, [], "127.0.0.1", True), False
        )
