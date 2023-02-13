from unittest import TestCase
from unittest.mock import patch

from splunk_connect_for_snmp.enrich.tasks import (
    enrich,
    enrich_metric_with_fields_from_db,
)

attributes = {
    "id": "GROUP1",
    "address": "192.168.0.1",
    "fields": {
        "SNMPv2-MIB|sysDescr": {
            "time": 1234,
            "type": "f",
            "value": "Linux zeus 4.8.6.5-smp #2 SMP Sun Nov 13 14:58:11 CDT 2016 i686",
            "oid": "1.3.6.1.2.1.1.1.0",
            "name": "SNMPv2-MIB.sysDescr",
        },
        "SNMPv2-MIB|sysObjectID": {
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
        "SNMPv2-MIB|sysDescr": {
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

input_enrich = {
    "time": 1676291976.2939305,
    "address": "54.91.99.113",
    "result": {
        "ENTITY-MIB::int=1": {
            "metrics": {},
            "fields": {
                "ENTITY-MIB.entPhysicalDescr": {
                    "time": 1676291974.9832206,
                    "type": "f",
                    "value": "Cisco CSR1000V Chassis",
                    "oid": "1.3.6.1.2.1.47.1.1.1.1.2.1",
                }
            },
            "profiles": "",
        },
        "CISCO-PROCESS-MIB::int=7": {
            "metrics": {
                "CISCO-PROCESS-MIB.cpmCPUMemoryFree": {
                    "time": 1676291974.981197,
                    "type": "g",
                    "value": 1575532.0,
                    "index": "7",
                    "oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.13.7",
                },
                "CISCO-PROCESS-MIB.cpmCPUMemoryUsed": {
                    "time": 1676291974.981377,
                    "type": "g",
                    "value": 2400532.0,
                    "index": "7",
                    "oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.12.7",
                },
            },
            "fields": {
                "CISCO-PROCESS-MIB.cpmCPULoadAvg1min": {
                    "time": 1676291974.981143,
                    "type": "f",
                    "value": 84.0,
                    "oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.24.7",
                },
                "CISCO-PROCESS-MIB.cpmCPULoadAvg15min": {
                    "time": 1676291974.9813292,
                    "type": "f",
                    "value": 91.0,
                    "oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.26.7",
                },
                "CISCO-PROCESS-MIB.cpmCPULoadAvg5min": {
                    "time": 1676291974.9814994,
                    "type": "f",
                    "value": 90.0,
                    "oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.25.7",
                },
            },
            "profiles": "DCN_profile",
        },
        "JUNIPER-IF-MIB::": {"metrics": {}, "fields": {}, "profiles": ""},
        "CISCO-ENTITY-SENSOR-MIB::": {"metrics": {}, "fields": {}, "profiles": ""},
        "ENTITY-MIB::int=10": {
            "metrics": {},
            "fields": {
                "ENTITY-MIB.entPhysicalDescr": {
                    "time": 1676291975.089646,
                    "type": "f",
                    "value": "Cisco CSR1000V Route Processor",
                    "oid": "1.3.6.1.2.1.47.1.1.1.1.2.10",
                }
            },
            "profiles": "",
        },
        "ENTITY-MIB::int=11": {
            "metrics": {},
            "fields": {
                "ENTITY-MIB.entPhysicalDescr": {
                    "time": 1676291975.3776612,
                    "type": "f",
                    "value": "CPU 0 of module R0",
                    "oid": "1.3.6.1.2.1.47.1.1.1.1.2.11",
                }
            },
            "profiles": "",
        },
        "ENTITY-MIB::int=12": {
            "metrics": {},
            "fields": {
                "ENTITY-MIB.entPhysicalDescr": {
                    "time": 1676291975.4914541,
                    "type": "f",
                    "value": "Network Management Ethernet",
                    "oid": "1.3.6.1.2.1.47.1.1.1.1.2.12",
                }
            },
            "profiles": "",
        },
        "ENTITY-MIB::int=30": {
            "metrics": {},
            "fields": {
                "ENTITY-MIB.entPhysicalDescr": {
                    "time": 1676291975.775517,
                    "type": "f",
                    "value": "Cisco CSR1000V Embedded Services Processor",
                    "oid": "1.3.6.1.2.1.47.1.1.1.1.2.30",
                }
            },
            "profiles": "",
        },
        "ENTITY-MIB::int=31": {
            "metrics": {},
            "fields": {
                "ENTITY-MIB.entPhysicalDescr": {
                    "time": 1676291975.9746468,
                    "type": "f",
                    "value": "QFP 0 of module F0",
                    "oid": "1.3.6.1.2.1.47.1.1.1.1.2.31",
                }
            },
            "profiles": "",
        },
        "ENTITY-MIB::int=61": {
            "metrics": {},
            "fields": {
                "ENTITY-MIB.entPhysicalDescr": {
                    "time": 1676291976.177441,
                    "type": "f",
                    "value": "Mapped to eth0 on VXE",
                    "oid": "1.3.6.1.2.1.47.1.1.1.1.2.61",
                }
            },
            "profiles": "",
        },
    },
    "detectchange": False,
    "frequency": 100,
}


@patch("splunk_connect_for_snmp.enrich.tasks.MONGO_UPDATE_BATCH_THRESHOLD", 2)
class TestEnrich(TestCase):
    @patch("pymongo.collection.Collection.find_one")
    @patch("pymongo.collection.Collection.update_one")
    @patch("pymongo.collection.Collection.bulk_write")
    @patch("splunk_connect_for_snmp.enrich.tasks.check_restart")
    def test_enrich(self, m_check_restart, bulk_write, m_update_one, m_find_one):
        current_target = {"address": "192.168.0.1"}
        m_find_one.side_effect = [current_target, True, attributes, attributes2, {}]

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
        bulk_write.assert_called()

        calls = m_update_one.call_args_list

        self.assertEqual(1, len(calls))

    @patch("pymongo.collection.Collection.find_one")
    @patch("pymongo.collection.Collection.update_one")
    @patch("pymongo.collection.Collection.bulk_write")
    @patch("splunk_connect_for_snmp.enrich.tasks.check_restart")
    def test_enrich_no_target(
        self, m_check_restart, bulk_write, m_update_one, m_find_one
    ):
        m_find_one.side_effect = [None, False]
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
                "name": "UDP-MIB.field2",
                "oid": "9.8.7.6",
                "time": 1640609779.473053,
                "type": "g",
                "value": "some_value2",
            },
            result["result"]["GROUP2"]["fields"]["UDP-MIB.field2"],
        )

        bulk_write.assert_called()
        self.assertEqual("192.168.0.1", result["address"])

    def test_enrich_metric_with_fields_from_db(self):
        additional_field = {
            "CISCO-PROCESS-MIB|extraField": {
                "time": 1676291974.981143,
                "type": "f",
                "value": "random_value",
                "oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.24.0.0.0.0.0",
                "name": "CISCO-PROCESS-MIB.extraField",
            }
        }
        snmp_object = input_enrich["result"].get("CISCO-PROCESS-MIB::int=7")
        enrich_metric_with_fields_from_db(snmp_object, additional_field)
        result = {
            "metrics": {
                "CISCO-PROCESS-MIB.cpmCPUMemoryFree": {
                    "time": 1676291974.981197,
                    "type": "g",
                    "value": 1575532.0,
                    "index": "7",
                    "oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.13.7",
                },
                "CISCO-PROCESS-MIB.cpmCPUMemoryUsed": {
                    "time": 1676291974.981377,
                    "type": "g",
                    "value": 2400532.0,
                    "index": "7",
                    "oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.12.7",
                },
            },
            "fields": {
                "CISCO-PROCESS-MIB.cpmCPULoadAvg1min": {
                    "time": 1676291974.981143,
                    "type": "f",
                    "value": 84.0,
                    "oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.24.7",
                },
                "CISCO-PROCESS-MIB.cpmCPULoadAvg15min": {
                    "time": 1676291974.9813292,
                    "type": "f",
                    "value": 91.0,
                    "oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.26.7",
                },
                "CISCO-PROCESS-MIB.cpmCPULoadAvg5min": {
                    "time": 1676291974.9814994,
                    "type": "f",
                    "value": 90.0,
                    "oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.25.7",
                },
                "CISCO-PROCESS-MIB.extraField": {
                    "time": 1676291974.981143,
                    "type": "f",
                    "value": "random_value",
                    "oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.24.0.0.0.0.0",
                    "name": "CISCO-PROCESS-MIB.extraField",
                },
            },
            "profiles": "DCN_profile",
        }
        self.assertEqual(result, snmp_object)

    def test_enrich_metric_with_fields_from_db_more_than_one(self):
        additional_field = {
            "CISCO-PROCESS-MIB|extraField": {
                "time": 1676291974.981143,
                "type": "f",
                "value": "random_value",
                "oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.24.0.0.0.0.0",
                "name": "CISCO-PROCESS-MIB.extraField",
            },
            "CISCO-PROCESS-MIB|extraFieldSecond": {
                "time": 1676291974.981143,
                "type": "f",
                "value": "random_value",
                "oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.24.0.0.0.0.0",
                "name": "CISCO-PROCESS-MIB.extraFieldSecond",
            }
        }
        snmp_object = input_enrich["result"].get("CISCO-PROCESS-MIB::int=7")
        enrich_metric_with_fields_from_db(snmp_object, additional_field)
        result = {
            "metrics": {
                "CISCO-PROCESS-MIB.cpmCPUMemoryFree": {
                    "time": 1676291974.981197,
                    "type": "g",
                    "value": 1575532.0,
                    "index": "7",
                    "oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.13.7",
                },
                "CISCO-PROCESS-MIB.cpmCPUMemoryUsed": {
                    "time": 1676291974.981377,
                    "type": "g",
                    "value": 2400532.0,
                    "index": "7",
                    "oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.12.7",
                },
            },
            "fields": {
                "CISCO-PROCESS-MIB.cpmCPULoadAvg1min": {
                    "time": 1676291974.981143,
                    "type": "f",
                    "value": 84.0,
                    "oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.24.7",
                },
                "CISCO-PROCESS-MIB.cpmCPULoadAvg15min": {
                    "time": 1676291974.9813292,
                    "type": "f",
                    "value": 91.0,
                    "oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.26.7",
                },
                "CISCO-PROCESS-MIB.cpmCPULoadAvg5min": {
                    "time": 1676291974.9814994,
                    "type": "f",
                    "value": 90.0,
                    "oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.25.7",
                },
                "CISCO-PROCESS-MIB.extraField": {
                    "time": 1676291974.981143,
                    "type": "f",
                    "value": "random_value",
                    "oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.24.0.0.0.0.0",
                    "name": "CISCO-PROCESS-MIB.extraField",
                },
                "CISCO-PROCESS-MIB.extraFieldSecond": {
                    "time": 1676291974.981143,
                    "type": "f",
                    "value": "random_value",
                    "oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.24.0.0.0.0.0",
                    "name": "CISCO-PROCESS-MIB.extraFieldSecond",
                },
            },
            "profiles": "DCN_profile",
        }
        self.assertEqual(result, snmp_object)
    def test_enrich_metric_with_fields_no_additional_fields(self):
        additional_field = {}
        snmp_object = input_enrich["result"].get("CISCO-PROCESS-MIB::int=7")
        result = snmp_object.copy()
        enrich_metric_with_fields_from_db(snmp_object, additional_field)
        self.assertEqual(result, snmp_object)

    def test_enrich_metric_with_fields_no_metrics(self):
        snmp_object = input_enrich["result"].get("ENTITY-MIB::int=1")
        additional_field = {
            "ENTITY-MIB|extraField": {
                "time": 1676291974.981143,
                "type": "f",
                "value": "random_value",
                "oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.24.0.0.0.0.0",
                "name": "ENTITY-MIB.extraField",
            }
        }
        result = snmp_object.copy()
        enrich_metric_with_fields_from_db(snmp_object, additional_field)
        self.assertEqual(result, snmp_object)