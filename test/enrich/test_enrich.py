from unittest import TestCase
from unittest.mock import patch

from splunk_connect_for_snmp.enrich.tasks import enrich

attributes = {
    "id": "GROUP1",
    "address": "192.168.0.1",
    "fields": {
        "9ebac3d8a4741756cc205c0ce00487cb662eb7e5b2d34499534a958a446b6814fa5782f00820bb6275fb6d7693e54aa5aea6075cdafd2d41780e92972680fde633a5e0377b0165cc0f59879c8e7801cda1b78305455a4968fac5ded2cdd2bebd174e0fb6c1deefac63af10d2f20b02ea833aaee42ae670a34b6fb6fe7ae761bf32a18b17fdb28e43f82644b8ae34a0d7d3d58dfe4ba05594a46d59107c5369eb10910127aab6a1920c760609170a3e2cf9cd238bdd697c4365f8a613e504e212df774011033b338183c7260fdf26dccbe69715cc6f331faa0c617c5195283af88087f7325a5a9169ce055cad8f9cf5c4b88a0dc337d6558cc712a822e524a2": {
            "time": 1234,
            "type": "f",
            "value": "Linux zeus 4.8.6.5-smp #2 SMP Sun Nov 13 14:58:11 CDT 2016 i686",
            "oid": "1.3.6.1.2.1.1.1.0",
            "name": "SNMPv2-MIB.sysDescr",
        },
        "43f8ebdee901cf02ea6a50ae765fac85784ec6e4bff4606a87100b5b80b17c8f666648f3f38d9af682f2ad94e1729ca600b6d82148885a4fa0efb4bf0206af5313fa8665e996b02af5d08ba8d72cf6ecc19dbc690a4bdb79bb3fe7ccbe5ae20776dabd6b258dcf70dbbc131b44656caa0e05f6475e30358a23280ccce69df7e35ba5134d15212d8b2474f4aa759fd239ad368da25fcf140a76679aac70d6c311407c6fa49ce0cd4f49d31d1dc3225794015cdf94ec2487cb9f7dfdd310ed31f67f73a1992e40aa17cdce80729b49cd3d9fd2615dd981b4ef7176dacd0fdf2222ece8c841468c3033252c9f1ebb48dd2e11dcbc08b0a8017dd130042bbd5f2a": {
            "time": 1234,
            "type": "r",
            "value": "SNMPv2-SMI::enterprises.8072.3.2.10",
            "oid": "1.3.6.1.2.1.1.2.0",
            "name": "SNMPv2-MIB.sysObjectID",
        },
        "14": {
            "time": 1234,
            "type": "r",
            "value": "SNMP Laboratories, info@snmplabs.com",
            "oid": "1.3.6.1.2.1.1.4.0",
            "name": "SNMPv2-MIB.sysContact",
        },
    },
}

attributes2 = {
    "id": "GROUP2",
    "address": "192.168.0.1",
    "fields": {
        "43f8ebdee901cf02ea6a50ae765fac85784ec6e4bff4606a87100b5b80b17c8f666648f3f38d9af682f2ad94e1729ca600b6d82148885a4fa0efb4bf0206af5313fa8665e996b02af5d08ba8d72cf6ecc19dbc690a4bdb79bb3fe7ccbe5ae20776dabd6b258dcf70dbbc131b44656caa0e05f6475e30358a23280ccce69df7e35ba5134d15212d8b2474f4aa759fd239ad368da25fcf140a76679aac70d6c311407c6fa49ce0cd4f49d31d1dc3225794015cdf94ec2487cb9f7dfdd310ed31f67f73a1992e40aa17cdce80729b49cd3d9fd2615dd981b4ef7176dacd0fdf2222ece8c841468c3033252c9f1ebb48dd2e11dcbc08b0a8017dd130042bbd5f2a": {
            "time": 1234,
            "type": "f",
            "value": "Linux zeus 4.8.6.5-smp #2 SMP Sun Nov 13 14:58:11 CDT 2016 i686",
            "oid": "1.3.6.1.2.1.1.1.0",
            "name": "SNMPv2-MIB.sysDescr",
        }
    },
}

input_dict = {
    "address": "192.168.0.1",
    "result": {
        "GROUP1": {
            "fields": {
                "SNMPv2-MIB.sysDescr": {
                    "oid": "1.3.6.1.2.1.1.1.0",
                    "time": 1234,
                    "type": "f",
                    "value": "Linux zeus 4.8.6.5-smp #2 SMP Sun Nov 13 14:58:11 CDT 2016 i686",
                }
            }
        },
        "GROUP2": {
            "fields": {
                "UDP-MIB.field2": {
                    "oid": "9.8.7.6",
                    "time": 1640609779.473053,
                    "type": "g",
                    "value": "some_value2",
                }
            }
        },
    },
}


@patch("splunk_connect_for_snmp.enrich.tasks.MONGO_UPDATE_BATCH_THRESHOLD", 2)
class TestEnrich(TestCase):
    @patch("pymongo.collection.Collection.find_one")
    @patch("pymongo.collection.Collection.update_one")
    @patch("splunk_connect_for_snmp.enrich.tasks.check_restart")
    def test_enrich(self, m_check_restart, m_update_one, m_find_one):
        current_target = {"address": "192.168.0.1"}
        m_find_one.side_effect = [current_target, attributes, attributes2, {}]

        result = enrich(input_dict)

        self.assertEqual(
            {
                "time": 1234,
                "type": "f",
                "value": "Linux zeus 4.8.6.5-smp #2 SMP Sun Nov 13 14:58:11 CDT 2016 i686",
                "oid": "1.3.6.1.2.1.1.1.0",
                "name": "SNMPv2-MIB.sysDescr",
            },
            result["result"]["GROUP1"]["fields"]["SNMPv2-MIB.sysDescr"],
        )

        self.assertEqual(
            {
                "time": 1234,
                "type": "r",
                "value": "SNMPv2-SMI::enterprises.8072.3.2.10",
                "oid": "1.3.6.1.2.1.1.2.0",
                "name": "SNMPv2-MIB.sysObjectID",
            },
            result["result"]["GROUP1"]["fields"]["SNMPv2-MIB.sysObjectID"],
        )

        self.assertEqual(
            {
                "time": 1234,
                "type": "r",
                "value": "SNMP Laboratories, info@snmplabs.com",
                "oid": "1.3.6.1.2.1.1.4.0",
                "name": "SNMPv2-MIB.sysContact",
            },
            result["result"]["GROUP1"]["fields"]["SNMPv2-MIB.sysContact"],
        )

        self.assertEqual("192.168.0.1", result["address"])

        m_check_restart.assert_called()

        calls = m_update_one.call_args_list

        self.assertEqual(2, len(calls))

    @patch("pymongo.collection.Collection.find_one")
    @patch("pymongo.collection.Collection.update_one")
    @patch("splunk_connect_for_snmp.enrich.tasks.check_restart")
    def test_enrich_no_target(self, m_check_restart, m_update_one, m_find_one):
        m_find_one.side_effect = [None, attributes, {}]
        result = enrich(input_dict)

        self.assertEqual(
            {
                "time": 1234,
                "type": "f",
                "value": "Linux zeus 4.8.6.5-smp #2 SMP Sun Nov 13 14:58:11 CDT 2016 i686",
                "oid": "1.3.6.1.2.1.1.1.0",
                "name": "SNMPv2-MIB.sysDescr",
            },
            result["result"]["GROUP1"]["fields"]["SNMPv2-MIB.sysDescr"],
        )

        self.assertEqual(
            {
                "time": 1234,
                "type": "r",
                "value": "SNMPv2-SMI::enterprises.8072.3.2.10",
                "oid": "1.3.6.1.2.1.1.2.0",
                "name": "SNMPv2-MIB.sysObjectID",
            },
            result["result"]["GROUP1"]["fields"]["SNMPv2-MIB.sysObjectID"],
        )

        self.assertEqual(
            {
                "time": 1234,
                "type": "r",
                "value": "SNMP Laboratories, info@snmplabs.com",
                "oid": "1.3.6.1.2.1.1.4.0",
                "name": "SNMPv2-MIB.sysContact",
            },
            result["result"]["GROUP1"]["fields"]["SNMPv2-MIB.sysContact"],
        )

        self.assertEqual("192.168.0.1", result["address"])
