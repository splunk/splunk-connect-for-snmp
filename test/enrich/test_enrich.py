from unittest import TestCase, mock
from unittest.mock import patch, Mock

from splunk_connect_for_snmp.enrich.tasks import enrich


class TestEnrich(TestCase):

    # @patch('pymongo.MongoClient')
    @patch("pymongo.collection.Collection.find_one")
    @patch("splunk_connect_for_snmp.enrich.tasks.check_restart")
    def test_enrich(self, m_check_restart, m_find_one):
        attributes = {
            "5f6b9ac8904073fcd07cfd4a2e095c7a79756206159682b9fed1333234883e7d0a1ca4c4b726cd37b7e40d3a48ad044c2f02c92d8512751518ba8b5ac579bcdc002e8fa813c83785a01c45c06541d612a05e8d454677f7607f57a7418ee83df7238c3dc8741587afc4d2a025ade13da6b156c6837999c4c6d262e9e95b13a40623da574da4fa8862fac5752d9f874abfc135d1127b2dbf4c32d031e12d22f15b47f8a2f24f0649fe09923e2af5096b8a0c7588a9cf8df7195e8e96a808ef367ef897704e8c65af8b289e855995d9bbbb217d243671cfb8963ced78dd0001b72687068e1aa9c63a9b0b6b3fa372ebdce2cc4244e3451103f04420e8f41b9cdf":
                {"id": "GROUP1",
                 "fields": {
                     "12": {"time": 1234, "type": "f",
                            "value": "Linux zeus 4.8.6.5-smp #2 SMP Sun Nov 13 14:58:11 CDT 2016 i686",
                            "oid": "1.3.6.1.2.1.1.1.0", "name": "SNMPv2-MIB.sysDescr"},
                     "13": {"time": 1234, "type": "r", "value": "SNMPv2-SMI::enterprises.8072.3.2.10",
                            "oid": "1.3.6.1.2.1.1.2.0", "name": "SNMPv2-MIB.sysObjectID"},
                     "14": {"time": 1234, "type": "r", "value": "SNMP Laboratories, info@snmplabs.com",
                            "oid": "1.3.6.1.2.1.1.4.0", "name": "SNMPv2-MIB.sysContact"}}}}

        current_target = {"address": "192.168.0.1", "attributes": attributes}
        # m_mongo_client.sc4snmp.targets.find_one.return_value = current_target
        # m_find_one.return_value = current_target
        m_find_one.return_value = current_target

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
