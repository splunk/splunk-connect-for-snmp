from tokenize import group
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch

from pysnmp.proto import rfc1902
from pysnmp.smi import builder, view
from pysnmp.smi.rfc1902 import ObjectIdentity, ObjectType

from splunk_connect_for_snmp.snmp.manager import Poller, describe_varbind


class TestProcessSnmpData(TestCase):
    @patch("splunk_connect_for_snmp.snmp.manager.is_mib_resolved")
    @patch("splunk_connect_for_snmp.snmp.manager.get_group_key")
    @patch("splunk_connect_for_snmp.snmp.manager.map_metric_type")
    @patch("splunk_connect_for_snmp.snmp.manager.extract_index_number")
    @patch("splunk_connect_for_snmp.snmp.manager.extract_indexes")
    @patch("time.time")
    def test_multiple_metrics_single_group(
        self,
        m_time,
        m_extract_indexes,
        m_extract_index_number,
        m_map_metric_type,
        m_get_group_key,
        m_resolved,
    ):
        poller = Poller.__new__(Poller)
        poller.builder = builder.MibBuilder()
        poller.mib_view_controller = view.MibViewController(poller.builder)

        m_resolved.return_value = True
        m_get_group_key.return_value = "QWERTYUIOP"
        m_map_metric_type.side_effect = ["g", "g"]
        m_extract_index_number.return_value = 1
        m_extract_indexes.return_value = [7]

        m_time.return_value = 1640609779.473053

        varbind_mock1_1 = Mock()
        varbind_mock1_2 = Mock()
        varbind_mock2_1 = Mock()
        varbind_mock2_2 = Mock()

        varbind_mock1_1.get_mib_symbol.return_value = "IF-MIB", "some_metric", 1
        varbind_mock1_1.prettyPrint.return_value = "some text"
        varbind_mock1_1.get_oid.return_value = "1.2.3.4.5.6.7"

        varbind_mock1_2.prettyPrint.return_value = 65

        varbind_mock2_1.get_mib_symbol.return_value = "UDP-MIB", "next_metric", 1
        varbind_mock2_1.prettyPrint.return_value = "some text2"
        varbind_mock2_1.get_oid.return_value = "9.8.7.6"

        varbind_mock2_2.prettyPrint.return_value = 123

        varbind_table = [
            (varbind_mock1_1, varbind_mock1_2),
            (varbind_mock2_1, varbind_mock2_2),
        ]
        metrics = {}
        mapping = {}

        poller.process_snmp_data(varbind_table, metrics, mapping)

        self.assertEqual(
            {
                "QWERTYUIOP": {
                    "indexes": [7],
                    "fields": {},
                    "metrics": {
                        "IF-MIB.some_metric": {
                            "oid": "1.2.3.4.5.6.7",
                            "time": 1640609779.473053,
                            "type": "g",
                            "value": 65.0,
                        },
                        "UDP-MIB.next_metric": {
                            "oid": "9.8.7.6",
                            "time": 1640609779.473053,
                            "type": "g",
                            "value": 123.0,
                        },
                    },
                }
            },
            metrics,
        )

    @patch("splunk_connect_for_snmp.snmp.manager.is_mib_resolved")
    @patch("splunk_connect_for_snmp.snmp.manager.get_group_key")
    @patch("splunk_connect_for_snmp.snmp.manager.map_metric_type")
    @patch("splunk_connect_for_snmp.snmp.manager.extract_index_number")
    @patch("splunk_connect_for_snmp.snmp.manager.extract_indexes")
    @patch("time.time")
    def test_multiple_metrics_multiple_groups(
        self,
        m_time,
        m_extract_indexes,
        m_extract_index_number,
        m_map_metric_type,
        m_get_group_key,
        m_resolved,
    ):
        poller = Poller.__new__(Poller)
        poller.builder = builder.MibBuilder()
        poller.mib_view_controller = view.MibViewController(poller.builder)

        m_resolved.return_value = True
        m_get_group_key.side_effect = ["GROUP1", "GROUP2"]
        m_map_metric_type.side_effect = ["g", "g"]
        m_extract_index_number.return_value = 1
        m_extract_indexes.return_value = [7]

        m_time.return_value = 1640609779.473053

        varbind_mock1_1 = Mock()
        varbind_mock1_2 = Mock()
        varbind_mock2_1 = Mock()
        varbind_mock2_2 = Mock()

        varbind_mock1_1.get_mib_symbol.return_value = "IF-MIB", "some_metric", 1
        varbind_mock1_1.prettyPrint.return_value = "some text"
        varbind_mock1_1.get_oid.return_value = "1.2.3.4.5.6.7"

        varbind_mock1_2.prettyPrint.return_value = 65

        varbind_mock2_1.get_mib_symbol.return_value = "UDP-MIB", "next_metric", 1
        varbind_mock2_1.prettyPrint.return_value = "some text2"
        varbind_mock2_1.get_oid.return_value = "9.8.7.6"

        varbind_mock2_2.prettyPrint.return_value = 123

        varbind_table = [
            (varbind_mock1_1, varbind_mock1_2),
            (varbind_mock2_1, varbind_mock2_2),
        ]
        metrics = {}
        mapping = {}

        poller.process_snmp_data(varbind_table, metrics, mapping)

        self.assertEqual(
            {
                "GROUP1": {
                    "indexes": [7],
                    "fields": {},
                    "metrics": {
                        "IF-MIB.some_metric": {
                            "oid": "1.2.3.4.5.6.7",
                            "time": 1640609779.473053,
                            "type": "g",
                            "value": 65.0,
                        }
                    },
                },
                "GROUP2": {
                    "indexes": [7],
                    "fields": {},
                    "metrics": {
                        "UDP-MIB.next_metric": {
                            "oid": "9.8.7.6",
                            "time": 1640609779.473053,
                            "type": "g",
                            "value": 123.0,
                        }
                    },
                },
            },
            metrics,
        )

    @patch("splunk_connect_for_snmp.snmp.manager.is_mib_resolved")
    @patch("splunk_connect_for_snmp.snmp.manager.get_group_key")
    @patch("splunk_connect_for_snmp.snmp.manager.map_metric_type")
    @patch("splunk_connect_for_snmp.snmp.manager.extract_index_number")
    @patch("splunk_connect_for_snmp.snmp.manager.extract_indexes")
    @patch("time.time")
    def test_metrics_and_fields(
        self,
        m_time,
        m_extract_indexes,
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
        m_extract_indexes.return_value = [7]

        m_time.return_value = 1640609779.473053

        varbind_mock1_1 = Mock()
        varbind_mock1_2 = Mock()
        varbind_mock2_1 = Mock()
        varbind_mock2_2 = Mock()

        varbind_mock1_1.get_mib_symbol.return_value = "IF-MIB", "some_metric", 1
        varbind_mock1_1.prettyPrint.return_value = "some text"
        varbind_mock1_1.get_oid.return_value = "1.2.3.4.5.6.7"

        varbind_mock1_2.prettyPrint.return_value = 65

        varbind_mock2_1.get_mib_symbol.return_value = "UDP-MIB", "some_field", 1
        varbind_mock2_1.prettyPrint.return_value = "some text2"
        varbind_mock2_1.get_oid.return_value = "9.8.7.6"

        varbind_mock2_2.prettyPrint.return_value = "up and running"

        varbind_table = [
            (varbind_mock1_1, varbind_mock1_2),
            (varbind_mock2_1, varbind_mock2_2),
        ]
        metrics = {}
        mapping = {}

        poller.process_snmp_data(varbind_table, metrics, mapping)

        self.assertEqual(
            {
                "GROUP1": {
                    "indexes": [7],
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
                        }
                    },
                }
            },
            metrics,
        )

    @patch("splunk_connect_for_snmp.snmp.manager.is_mib_resolved")
    @patch("splunk_connect_for_snmp.snmp.manager.get_group_key")
    @patch("splunk_connect_for_snmp.snmp.manager.map_metric_type")
    @patch("splunk_connect_for_snmp.snmp.manager.extract_index_number")
    @patch("splunk_connect_for_snmp.snmp.manager.extract_indexes")
    @patch("time.time")
    def test_metrics_with_profile(
        self,
        m_time,
        m_extract_indexes,
        m_extract_index_number,
        m_map_metric_type,
        m_get_group_key,
        m_resolved,
    ):
        poller = Poller.__new__(Poller)
        poller.builder = builder.MibBuilder()
        poller.mib_view_controller = view.MibViewController(poller.builder)

        m_resolved.return_value = True
        m_get_group_key.return_value = "QWERTYUIOP"
        m_map_metric_type.side_effect = ["g", "g"]
        m_extract_index_number.return_value = 1
        m_extract_indexes.return_value = [6, 7]

        m_time.return_value = 1640609779.473053

        varbind_mock1_1 = Mock()
        varbind_mock1_2 = Mock()
        varbind_mock2_1 = Mock()
        varbind_mock2_2 = Mock()

        varbind_mock1_1.get_mib_symbol.return_value = "IF-MIB", "some_metric", 1
        varbind_mock1_1.prettyPrint.return_value = "some text"
        varbind_mock1_1.get_oid.return_value = "1.2.3.4.5.6.7"

        varbind_mock1_2.prettyPrint.return_value = 65

        varbind_mock2_1.get_mib_symbol.return_value = "UDP-MIB", "next_metric", 1
        varbind_mock2_1.prettyPrint.return_value = "some text2"
        varbind_mock2_1.get_oid.return_value = "9.8.7.6"

        varbind_mock2_2.prettyPrint.return_value = 123

        varbind_table = [
            (varbind_mock1_1, varbind_mock1_2),
            (varbind_mock2_1, varbind_mock2_2),
        ]
        metrics = {}
        mapping = {
            "IF-MIB::some_metric": "profile1",
            "UDP-MIB::next_metric": "profile2",
        }

        poller.process_snmp_data(varbind_table, metrics, "some_target", mapping)

        self.assertEqual(
            {
                "QWERTYUIOP": {
                    "indexes": [6, 7],
                    "fields": {},
                    "metrics": {
                        "IF-MIB.some_metric": {
                            "oid": "1.2.3.4.5.6.7",
                            "time": 1640609779.473053,
                            "type": "g",
                            "value": 65.0,
                        },
                        "UDP-MIB.next_metric": {
                            "oid": "9.8.7.6",
                            "time": 1640609779.473053,
                            "type": "g",
                            "value": 123.0,
                        },
                    },
                    "profiles": ["profile1", "profile2"],
                }
            },
            metrics,
        )

    @patch("time.time", MagicMock(return_value=12345))
    def test_handle_metrics_add_fields(self):
        poller = Poller.__new__(Poller)
        group_key = "KEY"
        metric = "sysUpTime"
        metric_type = "ObjectIdentifier"
        metric_value = "1234567"
        metrics = {"KEY": {"metrics": {}, "fields": {}, "profiles": []}}
        mib = "SNMPv2-MIB"
        oid = "1.3.6.1.2.1.1.3.0"
        profile = "some_profile"

        poller.handle_metrics(
            group_key, metric, metric_type, metric_value, metrics, mib, oid, profile
        )
        self.assertEqual(
            metrics,
            {
                "KEY": {
                    "metrics": {},
                    "fields": {
                        "SNMPv2-MIB.sysUpTime": {
                            "time": 12345,
                            "type": "ObjectIdentifier",
                            "value": "1234567",
                            "oid": "1.3.6.1.2.1.1.3.0",
                        }
                    },
                    "profiles": [],
                },
            },
        )

    @patch("time.time", MagicMock(return_value=12345))
    def test_handle_metrics_add_metrics_float(self):
        poller = Poller.__new__(Poller)
        group_key = "KEY"
        metric = "sysNum"
        metric_type = "g"
        metric_value = 123.0
        metrics = {"KEY": {"metrics": {}, "fields": {}, "profiles": []}}
        mib = "SNMPv2-MIB"
        oid = "1.3.6.1.2.1.1.3.0"
        profile = "some_profile"

        poller.handle_metrics(
            group_key, metric, metric_type, metric_value, metrics, mib, oid, profile
        )
        self.assertEqual(
            metrics,
            {
                "KEY": {
                    "fields": {},
                    "metrics": {
                        "SNMPv2-MIB.sysNum": {
                            "time": 12345,
                            "type": "g",
                            "value": 123.0,
                            "oid": "1.3.6.1.2.1.1.3.0",
                        }
                    },
                    "profiles": ["some_profile"],
                }
            },
        )

    def test_set_profile_name_matching_varbind_id(self):
        poller = Poller.__new__(Poller)

        mapping = {
            "SNMPv2-MIB::sysDescr.0": "BaseDeviceData",
            "SNMPv2-MIB::sysName.0": "BaseData",
        }
        metric = "sysDescr"
        mib = "SNMPv2-MIB"
        varbind_id = "SNMPv2-MIB::sysDescr.0"
        profile = poller.set_profile_name(mapping, metric, mib, varbind_id)
        self.assertEqual(profile, "BaseDeviceData")

    def test_set_profile_name_matching_metric(self):
        poller = Poller.__new__(Poller)
        mapping = {
            "SNMPv2-MIB::sysDescr.0": "BaseDeviceData",
            "SNMPv2-MIB::sysName.0": "BaseData",
        }
        metric = "sysDescr"
        mib = "SNMPv2-MIB"
        varbind_id = ""
        profile = poller.set_profile_name(mapping, metric, mib, varbind_id)
        self.assertEqual(profile, "BaseDeviceData")

    def test_set_profile_name_matching_mib(self):
        poller = Poller.__new__(Poller)
        mapping = {
            "SNMPv2-MIB::sysDescr.0": "BaseDeviceData",
            "SNMPv2-MIB::sysName.0": "BaseData",
        }
        metric = "sysData"
        mib = "SNMPv2-MIB"
        varbind_id = ""
        profile = poller.set_profile_name(mapping, metric, mib, varbind_id)
        self.assertEqual(profile, "BaseDeviceData")

    def test_set_profile_name_no_match(self):
        poller = Poller.__new__(Poller)
        mapping = {
            "SNMPv2-MIB::sysDescr.0": "BaseDeviceData",
            "SNMPv2-MIB::sysName.0": "BaseData",
        }
        metric = "sysData"
        mib = "SNMPv3-MIB"
        varbind_id = ""
        profile = poller.set_profile_name(mapping, metric, mib, varbind_id)
        self.assertIsNone(profile)

    def test_match_mapping_to_profile_no_match(self):
        poller = Poller.__new__(Poller)
        mapping = {
            "IF-MIB::sysDescr.0": "BaseDevice",
            "SNMPv2-MIB::sysDescr.0": "BaseDeviceData",
            "SNMPv2-MIB::sysName.0": "BaseData",
        }
        mib = "SNMPv3-MIB"
        profile = None
        profile = poller.match_mapping_to_profile(mapping, mib, profile)
        self.assertIsNone(profile)

    def test_match_mapping_to_profile_match(self):
        poller = Poller.__new__(Poller)
        mapping = {
            "IF-MIB::sysDescr.0": "BaseDevice",
            "SNMPv2-MIB::sysDescr.0": "BaseDeviceData",
            "SNMPv2-MIB::sysName.0": "BaseData",
        }
        mib = "SNMPv2-MIB"
        profile = None
        profile = poller.match_mapping_to_profile(mapping, mib, profile)
        self.assertEqual(profile, "BaseDeviceData")

    @patch(
        "splunk_connect_for_snmp.snmp.manager.extract_indexes",
        MagicMock(return_value=[1]),
    )
    def test_handle_groupkey_without_metrics(self):
        poller = Poller.__new__(Poller)
        mapping = {
            "IF-MIB::sysDescr.0": "BaseDevice",
            "SNMPv2-MIB::sysDescr.0": "BaseDeviceData",
            "SNMPv2-MIB::sysName.0": "BaseData",
        }
        group_key = "SNMPv2-MIB::tuple=int=0"
        index = MagicMock()
        metrics = {}
        poller.handle_groupkey_without_metrics(group_key, index, mapping, metrics)
        self.assertEqual(
            metrics,
            {
                "SNMPv2-MIB::tuple=int=0": {
                    "indexes": [1],
                    "fields": {},
                    "metrics": {},
                    "profiles": [],
                }
            },
        )

    @patch(
        "splunk_connect_for_snmp.snmp.manager.extract_indexes",
        MagicMock(return_value=[1]),
    )
    def test_handle_groupkey_without_metrics_no_mapping(self):
        poller = Poller.__new__(Poller)
        mapping = {}
        group_key = "SNMPv2-MIB::tuple=int=0"
        index = MagicMock()
        metrics = {}
        poller.handle_groupkey_without_metrics(group_key, index, mapping, metrics)
        self.assertEqual(
            metrics,
            {"SNMPv2-MIB::tuple=int=0": {"indexes": [1], "fields": {}, "metrics": {}}},
        )


class _UnprintableValue:
    """Value whose prettyPrint() fails like SnmpAdminString with a mismatched type."""

    tagSet = "tags 0:0:2"
    _value = 5

    def prettyPrint(self):
        raise AttributeError(
            "'SnmpAdminString' object has no attribute 'getNamedValues'"
        )


class _UnprintableVarbind:
    """Varbind whose str() fails the same way as the value's prettyPrint()."""

    def __init__(self, oid, mib_symbol, value):
        identity = Mock()
        identity.get_oid.return_value = oid
        identity.prettyPrint.return_value = f"{mib_symbol[0]}::{mib_symbol[1]}.1"
        identity.get_mib_symbol.return_value = mib_symbol
        self._items = (identity, value)

    def __getitem__(self, item):
        return self._items[item]

    def __str__(self):
        return self[1].prettyPrint()


class TestDescribeVarbind(TestCase):
    def test_describe_varbind_does_not_raise_when_value_cannot_be_printed(self):
        varbind = _UnprintableVarbind(
            "1.3.6.1.4.1.9.9.719.1.9.35.1.4",
            ("CISCO-UNIFIED-COMPUTING-MIB", "cucsFaultDescription", 1),
            _UnprintableValue(),
        )

        with self.assertRaises(AttributeError):
            str(varbind)

        description = describe_varbind(varbind)

        self.assertIn("oid=1.3.6.1.4.1.9.9.719.1.9.35.1.4", description)
        self.assertIn(
            "name=CISCO-UNIFIED-COMPUTING-MIB::cucsFaultDescription.1", description
        )
        self.assertIn("value_class=_UnprintableValue", description)
        self.assertIn("value_tags=tags 0:0:2", description)
        self.assertIn("raw_value=5", description)
        self.assertIn(
            "pretty_value=<AttributeError: 'SnmpAdminString' object has no attribute "
            "'getNamedValues'>",
            description,
        )

    def test_describe_varbind_with_resolved_object_type(self):
        mib_builder = builder.MibBuilder()
        mib_builder.load_modules("SNMPv2-MIB")
        varbind = ObjectType(
            ObjectIdentity("1.3.6.1.2.1.1.5.0"), rfc1902.OctetString("router1")
        ).resolve_with_mib(view.MibViewController(mib_builder))

        description = describe_varbind(varbind)

        self.assertIn("oid=1.3.6.1.2.1.1.5.0", description)
        self.assertIn("name=SNMPv2-MIB::sysName.0", description)
        self.assertIn("value_class=DisplayString", description)
        self.assertIn("pretty_value=router1", description)

    def test_describe_varbind_with_unresolved_object_type(self):
        varbind = ObjectType(ObjectIdentity("1.3.6.1.2.1.1.5.0"))

        description = describe_varbind(varbind)

        self.assertIn("unreadable varbind ObjectType", description)
        self.assertIn("not fully initialized", description)

    def test_describe_varbind_with_unreadable_object(self):
        self.assertIn("unreadable varbind", describe_varbind(object()))


class TestProcessSnmpDataErrorLogging(TestCase):
    @patch("splunk_connect_for_snmp.snmp.manager.is_mib_resolved", return_value=True)
    @patch("splunk_connect_for_snmp.snmp.manager.get_group_key", return_value="KEY")
    @patch("splunk_connect_for_snmp.snmp.manager.map_metric_type", return_value="g")
    @patch("splunk_connect_for_snmp.snmp.manager.extract_index_number", return_value=1)
    @patch("splunk_connect_for_snmp.snmp.manager.extract_indexes", return_value=[1])
    @patch("time.time", return_value=1640609779.473053)
    def test_bad_varbind_is_logged_and_other_varbinds_are_kept(
        self, _time, _indexes, _index_number, _metric_type, _group_key, _resolved
    ):
        poller = Poller.__new__(Poller)
        bad = _UnprintableVarbind(
            "1.3.6.1.4.1.9.9.719.1.9.35.1.4",
            ("CISCO-UNIFIED-COMPUTING-MIB", "cucsFaultDescription", 1),
            _UnprintableValue(),
        )
        good_identity = Mock()
        good_identity.get_mib_symbol.return_value = ("IF-MIB", "ifInErrors", 1)
        good_identity.prettyPrint.return_value = "IF-MIB::ifInErrors.1"
        good_identity.get_oid.return_value = "1.3.6.1.2.1.2.2.1.14.1"
        good_value = Mock()
        good_value.prettyPrint.return_value = 7
        metrics = {}

        with self.assertLogs(
            "splunk_connect_for_snmp.snmp.manager", level="ERROR"
        ) as logs:
            poller.process_snmp_data(
                [bad, (good_identity, good_value)], metrics, "10.14.191.36", {}
            )

        output = "\n".join(logs.output)
        self.assertIn("Exception processing data from 10.14.191.36", output)
        self.assertIn(
            "name=CISCO-UNIFIED-COMPUTING-MIB::cucsFaultDescription.1", output
        )
        self.assertIn("oid=1.3.6.1.4.1.9.9.719.1.9.35.1.4", output)
        self.assertEqual(7.0, metrics["KEY"]["metrics"]["IF-MIB.ifInErrors"]["value"])
