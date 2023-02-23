from unittest import TestCase
from unittest.mock import Mock, patch

from splunk_connect_for_snmp.snmp.manager import Poller


class TestProcessSnmpData(TestCase):
    @patch("splunk_connect_for_snmp.snmp.manager.isMIBResolved")
    @patch("splunk_connect_for_snmp.snmp.manager.get_group_key")
    @patch("splunk_connect_for_snmp.snmp.manager.map_metric_type")
    @patch("splunk_connect_for_snmp.snmp.manager.extract_index_number")
    @patch("splunk_connect_for_snmp.snmp.manager.extract_index_oid_part")
    @patch("time.time")
    def test_multiple_metrics_single_group(
        self,
        m_time,
        m_extract_index_oid_part,
        m_extract_index_number,
        m_map_metric_type,
        m_get_group_key,
        m_resolved,
    ):
        poller = Poller.__new__(Poller)

        m_resolved.return_value = True
        m_get_group_key.return_value = "QWERTYUIOP"
        m_map_metric_type.side_effect = ["g", "g"]
        m_extract_index_number.return_value = 1
        m_extract_index_oid_part.side_effect = ["7", "7.6"]

        m_time.return_value = 1640609779.473053

        var_bind_mock1_1 = Mock()
        var_bind_mock1_2 = Mock()
        var_bind_mock2_1 = Mock()
        var_bind_mock2_2 = Mock()

        var_bind_mock1_1.getMibSymbol.return_value = "IF-MIB", "some_metric", 1
        var_bind_mock1_1.prettyPrint.return_value = "some text"
        var_bind_mock1_1.getOid.return_value = "1.2.3.4.5.6.7"

        var_bind_mock1_2.prettyPrint.return_value = 65

        var_bind_mock2_1.getMibSymbol.return_value = "UDP-MIB", "next_metric", 1
        var_bind_mock2_1.prettyPrint.return_value = "some text2"
        var_bind_mock2_1.getOid.return_value = "9.8.7.6"

        var_bind_mock2_2.prettyPrint.return_value = 123

        varBindTable = [
            (var_bind_mock1_1, var_bind_mock1_2),
            (var_bind_mock2_1, var_bind_mock2_2),
        ]
        metrics = {}
        mapping = {}

        poller.process_snmp_data(varBindTable, metrics, mapping)

        self.assertEqual(
            {
                "QWERTYUIOP": {
                    "fields": {},
                    "metrics": {
                        "IF-MIB.some_metric": {
                            "oid": "1.2.3.4.5.6.7",
                            "time": 1640609779.473053,
                            "type": "g",
                            "value": 65.0,
                            "index": "7",
                        },
                        "UDP-MIB.next_metric": {
                            "oid": "9.8.7.6",
                            "time": 1640609779.473053,
                            "type": "g",
                            "value": 123.0,
                            "index": "7.6",
                        },
                    },
                }
            },
            metrics,
        )

    @patch("splunk_connect_for_snmp.snmp.manager.isMIBResolved")
    @patch("splunk_connect_for_snmp.snmp.manager.get_group_key")
    @patch("splunk_connect_for_snmp.snmp.manager.map_metric_type")
    @patch("splunk_connect_for_snmp.snmp.manager.extract_index_number")
    @patch("splunk_connect_for_snmp.snmp.manager.extract_index_oid_part")
    @patch("time.time")
    def test_multiple_metrics_multiple_groups(
        self,
        m_time,
        m_extract_index_oid_part,
        m_extract_index_number,
        m_map_metric_type,
        m_get_group_key,
        m_resolved,
    ):
        poller = Poller.__new__(Poller)

        m_resolved.return_value = True
        m_get_group_key.side_effect = ["GROUP1", "GROUP2"]
        m_map_metric_type.side_effect = ["g", "g"]
        m_extract_index_number.return_value = 1
        m_extract_index_oid_part.side_effect = ["7", "6"]

        m_time.return_value = 1640609779.473053

        var_bind_mock1_1 = Mock()
        var_bind_mock1_2 = Mock()
        var_bind_mock2_1 = Mock()
        var_bind_mock2_2 = Mock()

        var_bind_mock1_1.getMibSymbol.return_value = "IF-MIB", "some_metric", 1
        var_bind_mock1_1.prettyPrint.return_value = "some text"
        var_bind_mock1_1.getOid.return_value = "1.2.3.4.5.6.7"

        var_bind_mock1_2.prettyPrint.return_value = 65

        var_bind_mock2_1.getMibSymbol.return_value = "UDP-MIB", "next_metric", 1
        var_bind_mock2_1.prettyPrint.return_value = "some text2"
        var_bind_mock2_1.getOid.return_value = "9.8.7.6"

        var_bind_mock2_2.prettyPrint.return_value = 123

        varBindTable = [
            (var_bind_mock1_1, var_bind_mock1_2),
            (var_bind_mock2_1, var_bind_mock2_2),
        ]
        metrics = {}
        mapping = {}

        poller.process_snmp_data(varBindTable, metrics, mapping)

        self.assertEqual(
            {
                "GROUP1": {
                    "fields": {},
                    "metrics": {
                        "IF-MIB.some_metric": {
                            "oid": "1.2.3.4.5.6.7",
                            "time": 1640609779.473053,
                            "type": "g",
                            "value": 65.0,
                            "index": "7",
                        }
                    },
                },
                "GROUP2": {
                    "fields": {},
                    "metrics": {
                        "UDP-MIB.next_metric": {
                            "oid": "9.8.7.6",
                            "time": 1640609779.473053,
                            "type": "g",
                            "value": 123.0,
                            "index": "6",
                        }
                    },
                },
            },
            metrics,
        )

    @patch("splunk_connect_for_snmp.snmp.manager.isMIBResolved")
    @patch("splunk_connect_for_snmp.snmp.manager.get_group_key")
    @patch("splunk_connect_for_snmp.snmp.manager.map_metric_type")
    @patch("splunk_connect_for_snmp.snmp.manager.extract_index_number")
    @patch("splunk_connect_for_snmp.snmp.manager.extract_index_oid_part")
    @patch("time.time")
    def test_metrics_and_fields(
        self,
        m_time,
        m_extract_index_oid_part,
        m_extract_index_number,
        m_map_metric_type,
        m_get_group_key,
        m_resolved,
    ):
        poller = Poller.__new__(Poller)

        m_resolved.return_value = True
        m_get_group_key.return_value = "GROUP1"
        m_map_metric_type.side_effect = ["g", "r"]
        m_extract_index_number.return_value = 1
        m_extract_index_oid_part.return_value = "6"

        m_time.return_value = 1640609779.473053

        var_bind_mock1_1 = Mock()
        var_bind_mock1_2 = Mock()
        var_bind_mock2_1 = Mock()
        var_bind_mock2_2 = Mock()

        var_bind_mock1_1.getMibSymbol.return_value = "IF-MIB", "some_metric", 1
        var_bind_mock1_1.prettyPrint.return_value = "some text"
        var_bind_mock1_1.getOid.return_value = "1.2.3.4.5.6.7"

        var_bind_mock1_2.prettyPrint.return_value = 65

        var_bind_mock2_1.getMibSymbol.return_value = "UDP-MIB", "some_field", 1
        var_bind_mock2_1.prettyPrint.return_value = "some text2"
        var_bind_mock2_1.getOid.return_value = "9.8.7.6"

        var_bind_mock2_2.prettyPrint.return_value = "up and running"

        varBindTable = [
            (var_bind_mock1_1, var_bind_mock1_2),
            (var_bind_mock2_1, var_bind_mock2_2),
        ]
        metrics = {}
        mapping = {}

        poller.process_snmp_data(varBindTable, metrics, mapping)

        self.assertEqual(
            {
                "GROUP1": {
                    "fields": {
                        "UDP-MIB.some_field": {
                            "oid": "9.8.7.6",
                            "time": 1640609779.473053,
                            "type": "r",
                            "value": "up and running",
                        }
                    },
                    "metrics": {
                        "IF-MIB.some_metric": {
                            "oid": "1.2.3.4.5.6.7",
                            "time": 1640609779.473053,
                            "type": "g",
                            "value": 65.0,
                            "index": "6",
                        }
                    },
                }
            },
            metrics,
        )

    @patch("splunk_connect_for_snmp.snmp.manager.isMIBResolved")
    @patch("splunk_connect_for_snmp.snmp.manager.get_group_key")
    @patch("splunk_connect_for_snmp.snmp.manager.map_metric_type")
    @patch("splunk_connect_for_snmp.snmp.manager.extract_index_number")
    @patch("splunk_connect_for_snmp.snmp.manager.extract_index_oid_part")
    @patch("time.time")
    def test_metrics_with_profile(
        self,
        m_time,
        m_extract_index_oid_part,
        m_extract_index_number,
        m_map_metric_type,
        m_get_group_key,
        m_resolved,
    ):
        poller = Poller.__new__(Poller)

        m_resolved.return_value = True
        m_get_group_key.return_value = "QWERTYUIOP"
        m_map_metric_type.side_effect = ["g", "g"]
        m_extract_index_number.return_value = 1
        m_extract_index_oid_part.side_effect = ["6.7", "6"]

        m_time.return_value = 1640609779.473053

        var_bind_mock1_1 = Mock()
        var_bind_mock1_2 = Mock()
        var_bind_mock2_1 = Mock()
        var_bind_mock2_2 = Mock()

        var_bind_mock1_1.getMibSymbol.return_value = "IF-MIB", "some_metric", 1
        var_bind_mock1_1.prettyPrint.return_value = "some text"
        var_bind_mock1_1.getOid.return_value = "1.2.3.4.5.6.7"

        var_bind_mock1_2.prettyPrint.return_value = 65

        var_bind_mock2_1.getMibSymbol.return_value = "UDP-MIB", "next_metric", 1
        var_bind_mock2_1.prettyPrint.return_value = "some text2"
        var_bind_mock2_1.getOid.return_value = "9.8.7.6"

        var_bind_mock2_2.prettyPrint.return_value = 123

        varBindTable = [
            (var_bind_mock1_1, var_bind_mock1_2),
            (var_bind_mock2_1, var_bind_mock2_2),
        ]
        metrics = {}
        mapping = {"IF-MIB::some_metric": "profile1", "UDP-MIB::next_metric": "profile2"}

        poller.process_snmp_data(varBindTable, metrics, "some_target", mapping)

        self.assertEqual(
            {
                "QWERTYUIOP": {
                    "fields": {},
                    "metrics": {
                        "IF-MIB.some_metric": {
                            "oid": "1.2.3.4.5.6.7",
                            "time": 1640609779.473053,
                            "type": "g",
                            "value": 65.0,
                            "index": "6.7",
                        },
                        "UDP-MIB.next_metric": {
                            "oid": "9.8.7.6",
                            "time": 1640609779.473053,
                            "type": "g",
                            "value": 123.0,
                            "index": "6",
                        },
                    },
                    "profiles": ["profile1", "profile2"],
                }
            },
            metrics,
        )
