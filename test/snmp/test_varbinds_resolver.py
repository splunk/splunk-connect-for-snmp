import unittest
from unittest.mock import MagicMock, patch

from pysnmp.smi.rfc1902 import ObjectType

from splunk_connect_for_snmp.snmp.varbinds_resolver import (
    Profile,
    Varbind,
    VarBindContainer,
)


class TestVarbind(unittest.TestCase):
    def test_init_with_list(self):
        varbind = Varbind(["SNMPv2-MIB", "sysDescr", "0"])
        self.assertEqual(varbind.list, ["SNMPv2-MIB", "sysDescr", "0"])
        self.assertIsInstance(varbind.object_identity, ObjectType)

    def test_init_with_string(self):
        varbind = Varbind("SNMPv2-MIB")
        self.assertEqual(varbind.list, ["SNMPv2-MIB"])
        self.assertIsInstance(varbind.object_identity, ObjectType)

    def test_mapping_key(self):
        varbind = Varbind(["SNMPv2-MIB", "sysDescr", "0"])
        self.assertEqual(varbind.mapping_key(), "SNMPv2-MIB::sysDescr.0")

    def test_mapping_key_multiple(self):
        varbind = Varbind(["TCP-MIB", "tcpListenerProcess", 0, 443])
        self.assertEqual(varbind.mapping_key(), "TCP-MIB::tcpListenerProcess.0.443")

    def test_repr(self):
        varbind = Varbind(["SNMPv2-MIB", "sysDescr", "0"])
        self.assertEqual(repr(varbind), "['SNMPv2-MIB', 'sysDescr', '0']")


class TestVarBindContainer(unittest.TestCase):
    def setUp(self):
        self.varbind_container = VarBindContainer()

    def test_add_varbind(self):
        varbind1 = Varbind(["IF-MIB", "ifInOctets", 1])
        self.varbind_container.insert_varbind(varbind1)
        self.assertIn(varbind1.mapping_key(), self.varbind_container.map)

        varbind2 = Varbind(["IP-MIB", "ipInReceives"])
        self.varbind_container.insert_varbind(varbind2)
        self.assertIn(varbind2.mapping_key(), self.varbind_container.map)

        varbind3 = Varbind(["IP-MIB", "ipInReceives", 1])
        self.varbind_container.insert_varbind(varbind3)
        self.assertNotIn(varbind3.mapping_key(), self.varbind_container.map)

        varbind4 = Varbind(["IF-MIB", "ifOutOctets"])
        self.varbind_container.insert_varbind(varbind4)
        self.assertIn(varbind4.mapping_key(), self.varbind_container.map)

    def test_return_varbind_keys(self):
        varbind1 = Varbind(["IF-MIB", "ifInOctets", 1])
        self.varbind_container.insert_varbind(varbind1)
        varbind2 = Varbind(["IP-MIB", "ipInReceives"])
        self.varbind_container.insert_varbind(varbind2)

        varbind_keys = self.varbind_container.return_varbind_keys()
        self.assertIn(varbind1.mapping_key(), varbind_keys)
        self.assertIn(varbind2.mapping_key(), varbind_keys)
        self.assertCountEqual(
            varbind_keys, ["IF-MIB::ifInOctets.1", "IP-MIB::ipInReceives"]
        )

    def test_return_varbind_values(self):
        varbind1 = Varbind(["IF-MIB", "ifInOctets", 1])
        self.varbind_container.insert_varbind(varbind1)
        varbind2 = Varbind(["IP-MIB", "ipInReceives"])
        self.varbind_container.insert_varbind(varbind2)

        varbind_values = self.varbind_container.return_varbind_values()
        self.assertIn(varbind1, varbind_values)
        self.assertIn(varbind2, varbind_values)

    def test_get_mib_families(self):
        varbind1 = Varbind(["IF-MIB", "ifInOctets", 1])
        self.varbind_container.insert_varbind(varbind1)
        varbind2 = Varbind(["IP-MIB", "ipInReceives"])
        self.varbind_container.insert_varbind(varbind2)

        mib_families = self.varbind_container.get_mib_families()
        self.assertIn("IF-MIB", mib_families)
        self.assertIn("IP-MIB", mib_families)

    def test_get_profile_mapping(self):
        profile_name = "profile1"
        varbind1 = Varbind(["IF-MIB", "ifInOctets", 1])
        self.varbind_container.insert_varbind(varbind1)
        varbind2 = Varbind(["IP-MIB", "ipInReceives"])
        self.varbind_container.insert_varbind(varbind2)

        profile_mapping = self.varbind_container.get_profile_mapping(profile_name)
        self.assertIn(varbind1.mapping_key(), profile_mapping)
        self.assertIn(varbind2.mapping_key(), profile_mapping)
        self.assertEqual(len(profile_mapping), 2)
        self.assertEqual(
            {"IF-MIB::ifInOctets.1": "profile1", "IP-MIB::ipInReceives": "profile1"},
            profile_mapping,
        )


class TestProfile(unittest.TestCase):
    def setUp(self):
        self.profile_dict = {
            "condition": {"type": "walk"},
            "varBinds": [["IF-MIB", "ifInOctets", 1]],
        }

    def test_init(self):
        name = "test"
        profile = Profile(name, self.profile_dict)
        self.assertEqual(profile.name, name)
        self.assertEqual(len(profile.varbinds), 1)

    def test_process(self):
        profile_dict = {
            "frequency": 30,
            "condition": {"type": "walk"},
            "varBinds": [["IF-MIB", "ifOutOctets", 1]],
        }
        profile = Profile("test", profile_dict)
        profile.process()
        expected_get_varbinds = VarBindContainer()
        expected_bulk_varbinds = VarBindContainer()
        expected_bulk_varbinds.insert_varbind(Varbind(["SNMPv2-MIB"]))
        expected_get_varbinds.insert_varbind(Varbind(["IF-MIB", "ifOutOctets", 1]))
        self.assertEqual(
            str(expected_bulk_varbinds.map), str(profile.varbinds_bulk.map)
        )
        self.assertEqual(str(expected_get_varbinds.map), str(profile.varbinds_get.map))

    def test_divide_on_bulk_and_get(self):
        profile = Profile("test", self.profile_dict)
        varbind = ["IF-MIB", "ifOutOctets", 1]
        profile.varbinds = [varbind]
        profile.divide_on_bulk_and_get()
        expected_result = {
            "IF-MIB::ifOutOctets.1": Varbind(["IF-MIB", "ifOutOctets", 1])
        }
        self.assertEqual(str(expected_result), str(profile.varbinds_get.map))

    def test_divide_on_bulk_and_get_many_elements(self):
        profile = Profile("test", self.profile_dict)
        varbinds = [
            ["IF-MIB", "ifOutOctets", 1],
            ["IP-MIB"],
            ["IP-MIB", "ipField"],
            ["TCP-MIB", "tcpField", 0, 1],
        ]
        profile.varbinds = varbinds
        profile.divide_on_bulk_and_get()
        expected_result_get = {
            "IF-MIB::ifOutOctets.1": Varbind(["IF-MIB", "ifOutOctets", 1]),
            "TCP-MIB::tcpField.0.1": Varbind(["TCP-MIB", "tcpField", 0, 1]),
        }
        expected_result_bulk = {"IP-MIB": Varbind(["IP-MIB"])}
        self.assertEqual(str(expected_result_get), str(profile.varbinds_get.map))
        self.assertEqual(str(expected_result_bulk), str(profile.varbinds_bulk.map))

    def test_get_varbinds(self):
        profile = Profile("test", self.profile_dict)
        profile.varbinds_bulk = VarBindContainer()
        profile.varbinds_bulk.insert_varbind(Varbind(["IF-MIB"]))
        profile.varbinds_bulk.insert_varbind(Varbind(["IP-MIB", "ipField"]))
        profile.varbinds_get = VarBindContainer()
        profile.varbinds_get.insert_varbind(Varbind(["TCP-MIB", "field1", 1]))
        profile.varbinds_get.insert_varbind(Varbind(["UDP-MIB", "fiel1d", 2]))
        varbinds_bulk, varbinds_get = profile.get_varbinds()
        self.assertEqual(varbinds_bulk, profile.varbinds_bulk)
        self.assertEqual(varbinds_get, profile.varbinds_get)

    def test_get_mib_families(self):
        profile = Profile("test", self.profile_dict)
        profile.varbinds_bulk = VarBindContainer()
        profile.varbinds_bulk.insert_varbind(Varbind(["IF-MIB"]))
        profile.varbinds_bulk.insert_varbind(Varbind(["IP-MIB", "ipField"]))
        profile.varbinds_get = VarBindContainer()
        profile.varbinds_get.insert_varbind(Varbind(["TCP-MIB", "field1", 1]))
        profile.varbinds_get.insert_varbind(Varbind(["UDP-MIB", "fiel1d", 2]))
        mib_families = profile.get_mib_families()
        self.assertEqual(mib_families, {"IF-MIB", "IP-MIB", "TCP-MIB", "UDP-MIB"})

    def test_add_profiles(self):
        profile_dict = {
            "frequency": 30,
            "condition": {"type": "walk"},
            "varBinds": [["IF-MIB", "ifOutOctets", 1]],
        }
        profile = Profile("test", profile_dict)
        profile.varbinds_get = VarBindContainer()
        profile.varbinds_bulk = VarBindContainer()
        profile.varbinds_bulk.insert_varbind(Varbind(["TCP-MIB", "field1", 1]))
        profile.varbinds_bulk.insert_varbind(Varbind(["UDP-MIB", "field2", 2]))
        profile.varbinds_bulk.insert_varbind(Varbind(["IF-MIB", "field3", 2]))
        profile.varbinds_bulk_mapping.update(
            {"TCP-MIB": "test", "UDP-MIB": "test", "IF-MIB": "test"}
        )

        profile2 = Profile("test2", profile_dict)
        profile2.varbinds_get = VarBindContainer()
        profile2.varbinds_bulk = VarBindContainer()
        profile2.varbinds_bulk.insert_varbind(Varbind(["TCP-MIB", "field1", 1]))
        profile2.varbinds_bulk.insert_varbind(Varbind(["UDP-MIB", "field3", 2]))
        profile2.varbinds_bulk_mapping.update({"TCP-MIB": "test2", "UDP-MIB": "test2"})

        profile3 = profile + profile2
        print(profile3.varbinds_bulk)
        varbinds = "{'IF-MIB::field3.2': ['IF-MIB', 'field3', 2], 'TCP-MIB::field1.1': ['TCP-MIB', 'field1', 1], 'UDP-MIB::field2.2': ['UDP-MIB', 'field2', 2], 'UDP-MIB::field3.2': ['UDP-MIB', 'field3', 2]}"
        self.assertEqual(profile3.name, "test:test2")
        self.assertEqual(str(profile3.varbinds_get), "{}")
        self.assertEqual(str(profile3.varbinds_bulk), varbinds)
        self.assertEqual(profile3.varbinds_get_mapping, {})
        self.assertEqual(
            profile3.varbinds_bulk_mapping,
            {"TCP-MIB": "test,test2", "UDP-MIB": "test,test2", "IF-MIB": "test"},
        )

    def test_add_mappings_does_not_mutate_inputs(self):
        profile = Profile("test", self.profile_dict)
        left_mapping = {
            "SNMPv2-MIB::sysName.0": "profile_a",
            "SNMPv2-MIB::sysContact.0": "profile_a",
        }
        right_mapping = {
            "SNMPv2-MIB::sysName.0": "profile_b",
            "SNMPv2-MIB::sysLocation.0": "profile_b",
        }
        original_left = left_mapping.copy()
        original_right = right_mapping.copy()

        result = profile.add_mappings(left_mapping, right_mapping)

        self.assertEqual(left_mapping, original_left)
        self.assertEqual(right_mapping, original_right)
        self.assertIsNot(result, left_mapping)
        self.assertIsNot(result, right_mapping)
        self.assertEqual(
            result,
            {
                "SNMPv2-MIB::sysName.0": "profile_a,profile_b",
                "SNMPv2-MIB::sysContact.0": "profile_a",
                "SNMPv2-MIB::sysLocation.0": "profile_b",
            },
        )

    def test_add_mappings_compares_complete_profile_names(self):
        profile = Profile("test", self.profile_dict)

        result = profile.add_mappings(
            {"SNMPv2-MIB::sysName.0": "profile_10"},
            {"SNMPv2-MIB::sysName.0": "profile_1"},
        )

        self.assertEqual(result["SNMPv2-MIB::sysName.0"], "profile_10,profile_1")

    def test_add_mappings_deduplicates_profiles_in_both_mappings(self):
        profile = Profile("test", self.profile_dict)
        mapping_key = "SNMPv2-MIB::sysName.0"
        cases = [
            (
                "profile_a,profile_b,profile_a",
                "profile_b,profile_a,profile_b",
                "profile_a,profile_b",
            ),
            (
                "profile_a,profile_b,profile_a",
                "profile_b,profile_c,profile_a,profile_c",
                "profile_a,profile_b,profile_c",
            ),
        ]

        for dict1_profiles, dict2_profiles, expected_profiles in cases:
            with self.subTest(
                dict1_profiles=dict1_profiles,
                dict2_profiles=dict2_profiles,
            ):
                result = profile.add_mappings(
                    {mapping_key: dict1_profiles},
                    {mapping_key: dict2_profiles},
                )

                self.assertEqual(result[mapping_key], expected_profiles)

    def test_repeated_profile_combinations_do_not_grow_cached_mappings(self):
        profile_body = {
            "frequency": 10,
            "varBinds": [
                ["SNMPv2-MIB", "sysName", 0],
                ["SNMPv2-MIB", "sysDescr"],
                ["IF-MIB", "ifDescr"],
            ],
        }
        profile_a = Profile("profile_a", profile_body)
        profile_b = Profile("profile_b", profile_body)
        profile_a.process()
        profile_b.process()

        for _ in range(10):
            combined_ab = profile_a + profile_b
            combined_ba = profile_b + profile_a

            self.assertEqual(
                combined_ab.varbinds_get_mapping["SNMPv2-MIB::sysName.0"],
                "profile_a,profile_b",
            )
            self.assertEqual(
                combined_ba.varbinds_get_mapping["SNMPv2-MIB::sysName.0"],
                "profile_b,profile_a",
            )
            self.assertEqual(
                combined_ab.varbinds_bulk_mapping["IF-MIB::ifDescr"],
                "profile_a,profile_b",
            )
            self.assertEqual(
                combined_ba.varbinds_bulk_mapping["IF-MIB::ifDescr"],
                "profile_b,profile_a",
            )

        self.assertEqual(
            profile_a.varbinds_get_mapping,
            {"SNMPv2-MIB::sysName.0": "profile_a"},
        )
        self.assertEqual(
            profile_b.varbinds_get_mapping,
            {"SNMPv2-MIB::sysName.0": "profile_b"},
        )
        self.assertEqual(
            profile_a.varbinds_bulk_mapping,
            {
                "SNMPv2-MIB::sysDescr": "profile_a",
                "IF-MIB::ifDescr": "profile_a",
            },
        )
        self.assertEqual(
            profile_b.varbinds_bulk_mapping,
            {
                "SNMPv2-MIB::sysDescr": "profile_b",
                "IF-MIB::ifDescr": "profile_b",
            },
        )

    @patch("splunk_connect_for_snmp.snmp.varbinds_resolver.logger")
    def test_add_mappings_logs_duplicate_decision(self, mock_logger):
        profile = Profile("test", self.profile_dict)

        result = profile.add_mappings(
            {"SNMPv2-MIB::sysName.0": "profile_a,profile_b"},
            {"SNMPv2-MIB::sysName.0": "profile_b,profile_a"},
        )

        self.assertEqual(result["SNMPv2-MIB::sysName.0"], "profile_a,profile_b")
        mock_logger.debug.assert_called_once_with(
            "Profile.add_mappings owner=test key=SNMPv2-MIB::sysName.0 "
            "dict1_profiles=['profile_a', 'profile_b'] "
            "dict2_profiles=['profile_b', 'profile_a'] "
            "added_profiles=[] result_profiles=['profile_a', 'profile_b']"
        )
