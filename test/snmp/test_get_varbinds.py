from unittest import TestCase
from unittest.mock import Mock

from splunk_connect_for_snmp.snmp.manager import Poller
from splunk_connect_for_snmp.snmp.varbinds_resolver import ProfileCollection


class TestGetVarbinds(TestCase):
    def test_get_varbinds_for_walk(self):
        poller = Poller.__new__(Poller)
        poller.profiles_collection = ProfileCollection({})
        poller.profiles_collection.process_profiles()
        poller.already_loaded_mibs = set()
        varbinds_get, get_mapping, varbinds_bulk, bulk_mapping = poller.get_var_binds(
            "192.168.0.1", walk=True
        )

        self.assertEqual(0, len(varbinds_get))
        self.assertEqual(1, len(varbinds_bulk))
        self.assertEqual(0, len(get_mapping))
        self.assertEqual(0, len(bulk_mapping))

        walk_var_bind = next(iter(varbinds_bulk))

        self.assertEqual(
            "1.3.6", walk_var_bind._ObjectType__args[0]._ObjectIdentity__args[0]
        )

    def test_get_varbinds_for_walk_redundant(self):
        poller = Poller.__new__(Poller)

        profiles = {
            "test1": {
                "condition": {"type": "walk"},
                "varBinds": [
                    ["IF-MIB", "ifInDiscards", 1],
                    ["IF-MIB", "ifOutErrors"],
                    ["SNMPv2-MIB", "sysDescr", 0],
                    ["IP-MIB"],
                ],
            }
        }

        poller.profiles = profiles
        poller.profiles_collection = ProfileCollection(profiles)
        poller.profiles_collection.process_profiles()
        poller.already_loaded_mibs = {}
        poller.load_mibs = Mock()
        varbinds_get, get_mapping, varbinds_bulk, bulk_mapping = poller.get_var_binds(
            "192.168.0.1", walk=True, profiles=["test1"]
        )
        self.assertEqual(1, len(varbinds_get))
        self.assertEqual(3, len(varbinds_bulk))
        self.assertEqual(0, len(get_mapping))
        self.assertEqual(0, len(bulk_mapping))

        walk_var_bind = list(varbinds_bulk)

        self.assertEqual(
            {
                walk_var_bind[0]._ObjectType__args[0]._ObjectIdentity__args[0],
                walk_var_bind[1]._ObjectType__args[0]._ObjectIdentity__args[0],
                walk_var_bind[2]._ObjectType__args[0]._ObjectIdentity__args[0],
            },
            {"SNMPv2-MIB", "IF-MIB", "IP-MIB"},
        )

    def test_get_varbinds_for_walk_none(self):
        poller = Poller.__new__(Poller)

        profiles = {
            "test1": {
                "condition": {"type": "walk"},
                "varBinds": [],
            }
        }

        poller.profiles = profiles
        poller.profiles_collection = ProfileCollection(profiles)
        poller.profiles_collection.process_profiles()
        poller.already_loaded_mibs = {}
        poller.load_mibs = Mock()
        varbinds_get, get_mapping, varbinds_bulk, bulk_mapping = poller.get_var_binds(
            "192.168.0.1", walk=True, profiles=["test1"]
        )
        self.assertEqual(0, len(varbinds_get))
        self.assertEqual(1, len(varbinds_bulk))
        self.assertEqual(0, len(get_mapping))
        self.assertEqual(0, len(bulk_mapping))

        walk_var_bind = list(varbinds_bulk)

        self.assertEqual(
            {
                walk_var_bind[0]._ObjectType__args[0]._ObjectIdentity__args[0],
            },
            {"SNMPv2-MIB"},
        )

    def test_get_varbinds_for_walk_with_three_profiles(self):
        poller = Poller.__new__(Poller)

        profiles = {
            "test1": {
                "condition": {"type": "walk"},
                "varBinds": [["IP-MIB"], ["TCP-MIB"], ["UDP-MIB"]],
            }
        }

        poller.profiles = profiles
        poller.profiles_collection = ProfileCollection(profiles)
        poller.profiles_collection.process_profiles()
        poller.already_loaded_mibs = {}
        poller.load_mibs = Mock()
        varbinds_get, get_mapping, varbinds_bulk, bulk_mapping = poller.get_var_binds(
            "192.168.0.1", walk=True, profiles=["test1"]
        )
        self.assertEqual(0, len(varbinds_get))
        self.assertEqual(4, len(varbinds_bulk))
        self.assertEqual(0, len(get_mapping))
        self.assertEqual(0, len(bulk_mapping))

        walk_var_bind = list(varbinds_bulk)

        self.assertEqual(
            {
                walk_var_bind[0]._ObjectType__args[0]._ObjectIdentity__args[0],
                walk_var_bind[1]._ObjectType__args[0]._ObjectIdentity__args[0],
                walk_var_bind[2]._ObjectType__args[0]._ObjectIdentity__args[0],
                walk_var_bind[3]._ObjectType__args[0]._ObjectIdentity__args[0],
            },
            {"SNMPv2-MIB", "UDP-MIB", "IP-MIB", "TCP-MIB"},
        )

    def test_get_varbinds_for_walk_next_time_no_profiles(self):
        poller = Poller.__new__(Poller)
        poller.profiles_collection = ProfileCollection({})
        varbinds_get, get_mapping, varbinds_bulk, bulk_mapping = poller.get_var_binds(
            "192.168.0.1", walk=True, profiles=[]
        )

        self.assertEqual(0, len(varbinds_get))
        self.assertEqual(1, len(varbinds_bulk))
        self.assertEqual(0, len(get_mapping))
        self.assertEqual(0, len(bulk_mapping))

        walk_var_bind = next(iter(varbinds_bulk))

        self.assertEqual(
            "1.3.6", walk_var_bind._ObjectType__args[0]._ObjectIdentity__args[0]
        )

    def test_get_varbinds_for_walk_with_profiles(self):
        profiles = {
            "profile1": {
                "condition": {"type": "walk"},
                "frequency": 20,
                "varBinds": [["IF-MIB"]],
            },
            "profile2": {
                "condition": {"type": "walk"},
                "frequency": 20,
                "varBinds": [["UDP-MIB"]],
            },
        }

        poller = Poller.__new__(Poller)
        poller.profiles = profiles
        poller.profiles_collection = ProfileCollection(profiles)
        poller.profiles_collection.process_profiles()
        poller.already_loaded_mibs = set()
        poller.load_mibs = Mock()

        varbinds_get, get_mapping, varbinds_bulk, bulk_mapping = poller.get_var_binds(
            "192.168.0.1", walk=True, profiles=["profile1"]
        )

        self.assertEqual(0, len(varbinds_get))
        self.assertEqual(2, len(varbinds_bulk))
        self.assertEqual(0, len(get_mapping))
        self.assertEqual(0, len(bulk_mapping))

        names = sorted(
            list(
                map(
                    lambda x: x._ObjectType__args[0]._ObjectIdentity__args[0],
                    varbinds_bulk,
                )
            )
        )

        self.assertEqual("IF-MIB", names[0])
        self.assertEqual("SNMPv2-MIB", names[1])

    def test_get_varbinds_for_walk_with_profiles_changed_sequence(self):
        profiles = {
            "profile1": {
                "condition": {"type": "walk"},
                "frequency": 20,
                "varBinds": [["IF-MIB"]],
            },
            "profile2": {
                "condition": {"type": "walk"},
                "frequency": 20,
                "varBinds": [["UDP-MIB"]],
            },
        }

        poller = Poller.__new__(Poller)
        poller.profiles = profiles
        poller.profiles_collection = ProfileCollection(profiles)
        poller.profiles_collection.process_profiles()
        poller.already_loaded_mibs = set()
        poller.load_mibs = Mock()

        varbinds_get, get_mapping, varbinds_bulk, bulk_mapping = poller.get_var_binds(
            "192.168.0.1", walk=True, profiles=["profile2"]
        )

        self.assertEqual(0, len(varbinds_get))
        self.assertEqual(2, len(varbinds_bulk))
        self.assertEqual(0, len(get_mapping))
        self.assertEqual(0, len(bulk_mapping))

        names = sorted(
            list(
                map(
                    lambda x: x._ObjectType__args[0]._ObjectIdentity__args[0],
                    varbinds_bulk,
                )
            )
        )

        self.assertEqual("SNMPv2-MIB", names[0])
        self.assertEqual("UDP-MIB", names[1])

    def test_get_varbinds_for_poll_family_only(self):
        poller = Poller.__new__(Poller)

        poller.profiles = {
            "profile1": {"frequency": 20, "varBinds": [["IF-MIB"]]},
            "profile2": {"frequency": 20, "varBinds": [["UDP-MIB"]]},
        }
        poller.profiles_collection = ProfileCollection(poller.profiles)
        poller.profiles_collection.process_profiles()
        poller.already_loaded_mibs = set()
        poller.load_mibs = Mock()

        profiles_requested = ["profile1", "profile2"]
        varbinds_get, get_mapping, varbinds_bulk, bulk_mapping = poller.get_var_binds(
            "192.168.0.1", profiles=profiles_requested
        )

        self.assertEqual(0, len(varbinds_get))
        self.assertEqual(2, len(varbinds_bulk))
        self.assertEqual(0, len(get_mapping))
        self.assertEqual(2, len(bulk_mapping))

        names = sorted(
            list(
                map(
                    lambda x: x._ObjectType__args[0]._ObjectIdentity__args[0],
                    varbinds_bulk,
                )
            )
        )

        self.assertEqual("IF-MIB", names[0])
        self.assertEqual("UDP-MIB", names[1])
        self.assertEqual({"IF-MIB": "profile1", "UDP-MIB": "profile2"}, bulk_mapping)
        poller.load_mibs.assert_called()
        self.assertCountEqual(poller.load_mibs.call_args.args[0], ["IF-MIB", "UDP-MIB"])

    def test_get_varbinds_for_poll_only_bulk_properties(self):
        poller = Poller.__new__(Poller)

        poller.profiles = {
            "profile1": {
                "frequency": 20,
                "varBinds": [["IF-MIB", "ifDescr"], ["IF-MIB", "ifSpeed"]],
            },
            "profile2": {"frequency": 20, "varBinds": [["UDP-MIB", "udpOutDatagrams"]]},
        }
        poller.load_mibs = Mock()
        poller.profiles_collection = ProfileCollection(poller.profiles)
        poller.profiles_collection.process_profiles()
        poller.already_loaded_mibs = set()
        profiles_requested = ["profile1", "profile2"]

        varbinds_get, get_mapping, varbinds_bulk, bulk_mapping = poller.get_var_binds(
            "192.168.0.1", profiles=profiles_requested
        )

        self.assertEqual(0, len(varbinds_get))
        self.assertEqual(3, len(varbinds_bulk))
        self.assertEqual(0, len(get_mapping))
        self.assertEqual(3, len(bulk_mapping))

        names = sorted(
            list(
                map(
                    lambda x: (
                        x._ObjectType__args[0]._ObjectIdentity__args[0],
                        x._ObjectType__args[0]._ObjectIdentity__args[1],
                    ),
                    varbinds_bulk,
                )
            )
        )

        self.assertEqual(("IF-MIB", "ifDescr"), names[0])
        self.assertEqual(("IF-MIB", "ifSpeed"), names[1])
        self.assertEqual(("UDP-MIB", "udpOutDatagrams"), names[2])

        self.assertEqual(
            {
                "IF-MIB::ifDescr": "profile1",
                "IF-MIB::ifSpeed": "profile1",
                "UDP-MIB::udpOutDatagrams": "profile2",
            },
            bulk_mapping,
        )
        poller.load_mibs.assert_called()
        self.assertCountEqual(poller.load_mibs.call_args.args[0], ["IF-MIB", "UDP-MIB"])

    def test_get_varbinds_for_poll_only_get_properties(self):
        poller = Poller.__new__(Poller)

        poller.profiles = {
            "profile1": {
                "frequency": 20,
                "varBinds": [["IF-MIB", "ifDescr", 0], ["IF-MIB", "ifDescr", 1]],
            },
            "profile2": {
                "frequency": 20,
                "varBinds": [["UDP-MIB", "udpOutDatagrams", 1]],
            },
        }
        poller.load_mibs = Mock()
        poller.profiles_collection = ProfileCollection(poller.profiles)
        poller.profiles_collection.process_profiles()
        poller.already_loaded_mibs = set()
        profiles_requested = ["profile1", "profile2"]

        varbinds_get, get_mapping, varbinds_bulk, bulk_mapping = poller.get_var_binds(
            "192.168.0.1", profiles=profiles_requested
        )

        self.assertEqual(3, len(varbinds_get))
        self.assertEqual(0, len(varbinds_bulk))
        self.assertEqual(3, len(get_mapping))
        self.assertEqual(0, len(bulk_mapping))

        names = sorted(
            list(
                map(
                    lambda x: (
                        x._ObjectType__args[0]._ObjectIdentity__args[0],
                        x._ObjectType__args[0]._ObjectIdentity__args[1],
                        x._ObjectType__args[0]._ObjectIdentity__args[2],
                    ),
                    varbinds_get,
                )
            )
        )

        self.assertEqual(("IF-MIB", "ifDescr", 0), names[0])
        self.assertEqual(("IF-MIB", "ifDescr", 1), names[1])
        self.assertEqual(("UDP-MIB", "udpOutDatagrams", 1), names[2])

        self.assertEqual(
            {
                "IF-MIB::ifDescr.0": "profile1",
                "IF-MIB::ifDescr.1": "profile1",
                "UDP-MIB::udpOutDatagrams.1": "profile2",
            },
            get_mapping,
        )
        poller.load_mibs.assert_called()
        self.assertCountEqual(poller.load_mibs.call_args.args[0], ["IF-MIB", "UDP-MIB"])

    def test_get_varbinds_for_poll_only_get_properties_compound(self):
        poller = Poller.__new__(Poller)

        poller.profiles = {
            "profile1": {
                "frequency": 20,
                "varBinds": [["IF-MIB", "ifDescr", 0], ["IF-MIB", "ifDescr", 1]],
            },
            "profile2": {
                "frequency": 20,
                "varBinds": [["TCP-MIB", "tcpListenerProcess", 0, 443]],
            },
        }
        poller.load_mibs = Mock()
        poller.profiles_collection = ProfileCollection(poller.profiles)
        poller.profiles_collection.process_profiles()
        poller.already_loaded_mibs = set()
        profiles_requested = ["profile1", "profile2"]

        varbinds_get, get_mapping, varbinds_bulk, bulk_mapping = poller.get_var_binds(
            "192.168.0.1", profiles=profiles_requested
        )

        self.assertEqual(3, len(varbinds_get))
        self.assertEqual(0, len(varbinds_bulk))
        self.assertEqual(3, len(get_mapping))
        self.assertEqual(0, len(bulk_mapping))

        names = sorted(
            list(
                map(
                    lambda x: (
                        x._ObjectType__args[0]._ObjectIdentity__args[0],
                        x._ObjectType__args[0]._ObjectIdentity__args[1],
                        x._ObjectType__args[0]._ObjectIdentity__args[2],
                    ),
                    varbinds_get,
                )
            )
        )

        self.assertEqual(("IF-MIB", "ifDescr", 0), names[0])
        self.assertEqual(("IF-MIB", "ifDescr", 1), names[1])
        self.assertEqual(
            ("TCP-MIB", "tcpListenerProcess", 0, 443),
            varbinds_get[2]._ObjectType__args[0]._ObjectIdentity__args,
        )

        self.assertEqual(
            {
                "IF-MIB::ifDescr.0": "profile1",
                "IF-MIB::ifDescr.1": "profile1",
                "TCP-MIB::tcpListenerProcess.0.443": "profile2",
            },
            get_mapping,
        )
        poller.load_mibs.assert_called()
        self.assertCountEqual(poller.load_mibs.call_args.args[0], ["IF-MIB", "TCP-MIB"])

    def test_get_varbinds_for_poll_shadowed_by_family(self):
        poller = Poller.__new__(Poller)

        poller.profiles = {
            "profile1": {
                "frequency": 20,
                "varBinds": [
                    ["UDP-MIB"],
                    ["UDP-MIB", "udpOutDatagrams"],
                    ["UDP-MIB", "udpOutDatagrams", 0],
                ],
            },
            "profile2": {
                "frequency": 20,
                "varBinds": [
                    ["IF-MIB"],
                    ["IF-MIB", "ifDescr"],
                    ["IF-MIB", "ifDescr", 1],
                ],
            },
        }
        poller.load_mibs = Mock()
        poller.profiles_collection = ProfileCollection(poller.profiles)
        poller.profiles_collection.process_profiles()
        poller.already_loaded_mibs = set()
        profiles_requested = ["profile1", "profile2"]

        varbinds_get, get_mapping, varbinds_bulk, bulk_mapping = poller.get_var_binds(
            "192.168.0.1", profiles=profiles_requested
        )

        self.assertEqual(0, len(varbinds_get))
        self.assertEqual(2, len(varbinds_bulk))
        self.assertEqual(0, len(get_mapping))
        self.assertEqual(2, len(bulk_mapping))

        names = sorted(
            list(
                map(
                    lambda x: (x._ObjectType__args[0]._ObjectIdentity__args[0]),
                    varbinds_bulk,
                )
            )
        )

        self.assertEqual("IF-MIB", names[0])
        self.assertEqual("UDP-MIB", names[1])

        self.assertEqual({"IF-MIB": "profile2", "UDP-MIB": "profile1"}, bulk_mapping)
        poller.load_mibs.assert_called()
        self.assertCountEqual(poller.load_mibs.call_args.args[0], ["IF-MIB", "UDP-MIB"])

    def test_get_varbinds_for_poll_shadowed_by_bulk_name(self):
        poller = Poller.__new__(Poller)

        poller.profiles = {
            "profile1": {
                "frequency": 20,
                "varBinds": [
                    ["UDP-MIB", "udpOutDatagrams"],
                    ["UDP-MIB", "udpOutDatagrams", 0],
                ],
            }
        }
        poller.load_mibs = Mock()
        poller.profiles_collection = ProfileCollection(poller.profiles)
        poller.profiles_collection.process_profiles()
        poller.already_loaded_mibs = set()
        profiles_requested = ["profile1"]

        varbinds_get, get_mapping, varbinds_bulk, bulk_mapping = poller.get_var_binds(
            "192.168.0.1", profiles=profiles_requested
        )

        self.assertEqual(0, len(varbinds_get))
        self.assertEqual(1, len(varbinds_bulk))
        self.assertEqual(0, len(get_mapping))
        self.assertEqual(1, len(bulk_mapping))

        names = sorted(
            list(
                map(
                    lambda x: (
                        x._ObjectType__args[0]._ObjectIdentity__args[0],
                        x._ObjectType__args[0]._ObjectIdentity__args[1],
                    ),
                    varbinds_bulk,
                )
            )
        )

        self.assertEqual(("UDP-MIB", "udpOutDatagrams"), names[0])

        self.assertEqual({"UDP-MIB::udpOutDatagrams": "profile1"}, bulk_mapping)

        poller.load_mibs.assert_called_with(["UDP-MIB"])

    def test_get_varbind_chunk(self):
        poller = Poller.__new__(Poller)

        initial_list = list(range(1, 13))
        expected_result = [[1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12]]
        expected_result_4 = [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12]]
        expected_result_5 = [[1, 2, 3, 4, 5], [6, 7, 8, 9, 10], [11, 12]]

        self.assertEqual(
            list(poller.get_varbind_chunk(initial_list, 3)), expected_result
        )
        self.assertEqual(
            list(poller.get_varbind_chunk(initial_list, 4)), expected_result_4
        )
        self.assertEqual(
            list(poller.get_varbind_chunk(initial_list, 5)), expected_result_5
        )
        self.assertEqual([], [])
