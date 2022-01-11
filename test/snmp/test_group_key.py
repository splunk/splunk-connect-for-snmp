from unittest import TestCase
from unittest.mock import Mock

from pysnmp.proto.rfc1902 import ObjectName

from splunk_connect_for_snmp.snmp.manager import get_group_key


class TestGroupKey(TestCase):

    def test_group_key_simple(self):
        mock1 = Mock()
        mock2 = Mock()

        mock1._value = 2
        mock2._value = 3

        index = (mock1, mock2)
        key = get_group_key("some-mib", "1.2.3.4.5", index)
        self.assertEqual('some-mib::int=2;int=3', key)

    def test_group_key_tuple_exception(self):
        mock1 = Mock()
        mock2 = Mock()
        mock3 = 2

        mock2._value = "value1"

        mock1._value = (mock2, mock3)

        index = [mock1]
        key = get_group_key("some-mib", "1.2.3.4.5", index)
        self.assertEqual('some-mib::tuple=Mock=value1|int=2', key)

    def test_group_key_tuple(self):
        mock1 = Mock()
        mock2 = Mock()
        mock3 = Mock()

        mock2._value = "value1"
        mock3._value = "value2"

        mock1._value = (mock2, mock3)

        index = [mock1]
        key = get_group_key("some-mib", "1.2.3.4.5", index)
        self.assertEqual('some-mib::tuple=Mock=value1|Mock=value2', key)


    def test_group_key_object_name(self):
        mock1 = Mock()

        mock1._value = ObjectName("1.2.3.4.5")

        index = [mock1]
        key = get_group_key("some-mib", "1.2.3.4.5", index)
        self.assertEqual('some-mib::ObjectName=1.2.3.4.5', key)