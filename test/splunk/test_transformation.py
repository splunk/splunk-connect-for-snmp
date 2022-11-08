from typing import Dict, List
from unittest import TestCase
from unittest.mock import patch

from splunk_connect_for_snmp.splunk.tasks import (
    transform_fields_and_metrics,
    transform_to_o11y,
)


class TestTransformation(TestCase):

    WORK_ITEM = {
        "time": 1666971087.4344501,
        "result": {
            "SNMPv2-MIB::tuple=int=0": {
                "metrics": {
                    "SNMPv2-MIB.sysUpTime": {
                        "time": 1666971087.4344132,
                        "type": "cc",
                        "value": 460809.0,
                        "oid": "1.3.6.1.2.1.1.3.0",
                    }
                },
                "fields": {
                    "SNMPv2-MIB.snmpTrapOID": {
                        "time": 1666971087.4344482,
                        "type": "r",
                        "value": "T11-GS-SERVER-SESSION-MIB::t11GssMIBObjects",
                        "oid": "1.3.6.1.6.3.1.1.4.1.0",
                    }
                },
            }
        },
        "address": "10.202.20.196",
        "detectchange": False,
        "sourcetype": "sc4snmp:traps",
    }

    def test_transform_fields_and_metrics(self):
        work = TestTransformation.WORK_ITEM.get("result").get("SNMPv2-MIB::tuple=int=0")
        processed = transform_fields_and_metrics(work)
        self.assertEqual(
            processed,
            {
                "SNMPv2-MIB.sysUpTime": {
                    "oid": "1.3.6.1.2.1.1.3.0",
                    "time": 1666971087.4344132,
                    "type": "cc",
                    "value": 460809.0,
                }
            },
        )

    def test_transform_to_o11y(self):
        expected_output = {
            "SNMPv2-MIB_sysUpTime": "460809.0",
            "SNMPv2-MIB_sysUpTime_time": "1666971087.4344132",
            "SNMPv2-MIB_snmpTrapOID": "T11-GS-SERVER-SESSION-MIB::t11GssMIBObjects",
            "SNMPv2-MIB_snmpTrapOID_time": "1666971087.4344482",
        }
        work_items = {
            "SNMPv2-MIB.sysUpTime": {
                "oid": "1.3.6.1.2.1.1.3.0",
                "time": 1666971087.4344132,
                "type": "cc",
                "value": 460809.0,
            },
            "SNMPv2-MIB.snmpTrapOID": {
                "time": 1666971087.4344482,
                "type": "r",
                "value": "T11-GS-SERVER-SESSION-MIB::t11GssMIBObjects",
                "oid": "1.3.6.1.6.3.1.1.4.1.0",
            },
        }
        self.assertEqual(transform_to_o11y(work_items), expected_output)

