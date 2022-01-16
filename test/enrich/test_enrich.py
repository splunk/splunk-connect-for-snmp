from unittest import TestCase, mock
from unittest.mock import patch, Mock

from splunk_connect_for_snmp.enrich.tasks import enrich


class TestEnrich(TestCase):

    @patch("pymongo.collection.Collection.find_one")
    @patch("pymongo.collection.Collection.update_one")
    @patch("splunk_connect_for_snmp.enrich.tasks.check_restart")
    def test_enrich(self, m_check_restart, m_update_one, m_find_one):
        attributes = {"id": "GROUP1",
                      "address": "192.168.0.1",
                      "fields": {
                          "12": {"time": 1234, "type": "f",
                                 "value": "Linux zeus 4.8.6.5-smp #2 SMP Sun Nov 13 14:58:11 CDT 2016 i686",
                                 "oid": "1.3.6.1.2.1.1.1.0", "name": "SNMPv2-MIB.sysDescr"},
                          "13": {"time": 1234, "type": "r", "value": "SNMPv2-SMI::enterprises.8072.3.2.10",
                                 "oid": "1.3.6.1.2.1.1.2.0", "name": "SNMPv2-MIB.sysObjectID"},
                          "14": {"time": 1234, "type": "r", "value": "SNMP Laboratories, info@snmplabs.com",
                                 "oid": "1.3.6.1.2.1.1.4.0", "name": "SNMPv2-MIB.sysContact"}}}

        current_target = {"address": "192.168.0.1"}
        m_find_one.side_effect = [current_target, attributes, {}]

        input_dict = {"address": "192.168.0.1",
                      "result": {'GROUP1': {'fields': {'IF-MIB.field1': {'oid': '1.2.3.4.5.6.7',
                                                                         'time': 1640609779.473053,
                                                                         'type': 'g',
                                                                         'value': "some_value1"}}},
                                 'GROUP2': {'fields': {'UDP-MIB.field2': {'oid': '9.8.7.6',
                                                                          'time': 1640609779.473053,
                                                                          'type': 'g',
                                                                          'value': "some_value2"}}}}}

        result = enrich(input_dict)

        self.assertEqual(
            {'time': 1234, 'type': 'f', 'value': 'Linux zeus 4.8.6.5-smp #2 SMP Sun Nov 13 14:58:11 CDT 2016 i686',
             'oid': '1.3.6.1.2.1.1.1.0', 'name': 'SNMPv2-MIB.sysDescr'},
            result["result"]["GROUP1"]["fields"]["SNMPv2-MIB.sysDescr"])

        self.assertEqual(
            {'time': 1234, 'type': 'r', 'value': 'SNMPv2-SMI::enterprises.8072.3.2.10', 'oid': '1.3.6.1.2.1.1.2.0',
             'name': 'SNMPv2-MIB.sysObjectID'}, result["result"]["GROUP1"]["fields"]['SNMPv2-MIB.sysObjectID'])

        self.assertEqual(
            {'time': 1234, 'type': 'r', 'value': 'SNMP Laboratories, info@snmplabs.com', 'oid': '1.3.6.1.2.1.1.4.0',
             'name': 'SNMPv2-MIB.sysContact'}, result["result"]["GROUP1"]["fields"]['SNMPv2-MIB.sysContact'])

        self.assertEqual("192.168.0.1", result["address"])

        m_check_restart.assert_called()
