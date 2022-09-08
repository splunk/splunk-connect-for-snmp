from unittest import TestCase

from splunk_connect_for_snmp.common.inventory_record import InventoryRecord


class TestInventoryRecord(TestCase):
    def test_address_not_none(self):
        ir_dict = {"address": None}

        with self.assertRaises(ValueError) as e:
            InventoryRecord(**ir_dict)
        self.assertEqual(
            "field address cannot be null", e.exception.args[0][0].exc.args[0]
        )

    def test_address_not_commented(self):
        ir_dict = {"address": "#asd"}

        with self.assertRaises(ValueError) as e:
            InventoryRecord(**ir_dict)
        self.assertEqual(
            "field address cannot be commented", e.exception.args[0][0].exc.args[0]
        )

    def test_address_not_resolvable(self):
        ir_dict = {"address": "12313sdfsf"}

        with self.assertRaises(ValueError) as e:
            InventoryRecord(**ir_dict)
        self.assertEqual(
            "field address must be an IP or a resolvable hostname 12313sdfsf",
            e.exception.args[0][0].exc.args[0],
        )

    def test_port_too_high(self):
        ir_dict = {
            "address": "192.168.0.1",
            "port": 65537,
            "version": "2c",
            "walk_interval": 1850,
            "smart_profiles": True,
            "delete": "",
        }

        with self.assertRaises(ValueError) as e:
            InventoryRecord(**ir_dict)
        self.assertEqual("Port out of range 65537", e.exception.args[0][0].exc.args[0])

    def test_port_not_specified(self):
        ir_dict = {
            "address": "192.168.0.1",
            "port": "",
            "version": None,
            "community": "public",
            "secret": "secret",
            "security_engine": "ENGINE",
            "walk_interval": 1850,
            "profiles": "",
            "smart_profiles": True,
            "delete": False,
        }
        ir = InventoryRecord(**ir_dict)
        self.assertEqual(161, ir.port)

    def test_version_none(self):
        ir_dict = {
            "address": "192.168.0.1",
            "port": "34",
            "version": None,
            "community": "public",
            "secret": "secret",
            "security_engine": "ENGINE",
            "walk_interval": 1850,
            "profiles": "",
            "smart_profiles": True,
            "delete": False,
        }

        ir = InventoryRecord(**ir_dict)

        self.assertEqual("2c", ir.version)

    def test_version_out_of_range(self):
        ir_dict = {
            "address": "192.168.0.1",
            "port": "34",
            "version": "5a",
            "community": "public",
            "secret": "secret",
            "security_engine": "ENGINE",
            "walk_interval": 1850,
            "profiles": "",
            "smart_profiles": True,
            "delete": False,
        }

        with self.assertRaises(ValueError) as e:
            InventoryRecord(**ir_dict)
        self.assertEqual(
            "version out of range 5a accepted is 1 or 2c or 3",
            e.exception.args[0][0].exc.args[0],
        )

    def test_empty_community(self):
        ir_dict = {
            "address": "192.168.0.1",
            "port": "34",
            "version": "3",
            "community": "",
            "secret": "secret",
            "security_engine": "ENGINE",
            "walk_interval": 1850,
            "profiles": "",
            "smart_profiles": True,
            "delete": False,
        }

        ir = InventoryRecord(**ir_dict)
        self.assertIsNone(ir.community)

    def test_empty_walk_interval(self):
        ir_dict = {
            "address": "192.168.0.1",
            "port": "34",
            "version": "3",
            "community": "public",
            "secret": "secret",
            "security_engine": "ENGINE",
            "walk_interval": None,
            "profiles": "",
            "smart_profiles": True,
            "delete": False,
        }

        ir = InventoryRecord(**ir_dict)
        self.assertEqual(42000, ir.walk_interval)

    def test_too_low_walk_interval(self):
        ir_dict = {
            "address": "192.168.0.1",
            "port": "34",
            "version": "3",
            "community": "public",
            "secret": "secret",
            "security_engine": "ENGINE",
            "walk_interval": 20,
            "profiles": "",
            "smart_profiles": True,
            "delete": False,
        }

        ir = InventoryRecord(**ir_dict)
        self.assertEqual(1800, ir.walk_interval)

    def test_too_high_walk_interval(self):
        ir_dict = {
            "address": "192.168.0.1",
            "port": "34",
            "version": "3",
            "community": "public",
            "secret": "secret",
            "security_engine": "ENGINE",
            "walk_interval": 50000,
            "profiles": "",
            "smart_profiles": True,
            "delete": False,
        }

        ir = InventoryRecord(**ir_dict)
        self.assertEqual(42000, ir.walk_interval)

    def test_profiles_not_string(self):
        ir_dict = {
            "address": "192.168.0.1",
            "port": "34",
            "version": "3",
            "community": "public",
            "secret": "secret",
            "security_engine": "ENGINE",
            "walk_interval": 1850,
            "profiles": [],
            "smart_profiles": True,
            "delete": False,
        }

        ir = InventoryRecord(**ir_dict)
        self.assertEqual([], ir.profiles)

    def test_smart_profiles_empty(self):
        ir_dict = {
            "address": "192.168.0.1",
            "port": "34",
            "version": "3",
            "community": "public",
            "secret": "secret",
            "security_engine": "ENGINE",
            "walk_interval": 1850,
            "profiles": "",
            "smart_profiles": True,
            "delete": False,
        }

        ir = InventoryRecord(**ir_dict)
        self.assertTrue(ir.smart_profiles)

    def test_delete_empty(self):
        ir_dict = {
            "address": "192.168.0.1",
            "port": "34",
            "version": "3",
            "community": "public",
            "secret": "secret",
            "security_engine": "ENGINE",
            "walk_interval": 1850,
            "profiles": "",
            "smart_profiles": True,
            "delete": "",
        }

        ir = InventoryRecord(**ir_dict)
        self.assertFalse(ir.delete)

    def test_port_too_high_camel_case(self):
        ir_dict = {
            "address": "192.168.0.1",
            "port": 65537,
            "version": "2c",
            "walk_interval": 1850,
            "SmartProfiles": True,
            "delete": "",
        }

        with self.assertRaises(ValueError) as e:
            InventoryRecord(**ir_dict)
        self.assertEqual("Port out of range 65537", e.exception.args[0][0].exc.args[0])

    def test_version_none_camel_case(self):
        ir_dict = {
            "address": "192.168.0.1",
            "port": "34",
            "version": None,
            "community": "public",
            "secret": "secret",
            "securityEngine": "ENGINE",
            "walk_interval": 1850,
            "profiles": "",
            "SmartProfiles": True,
            "delete": False,
        }

        ir = InventoryRecord(**ir_dict)

        self.assertEqual("2c", ir.version)

    def test_version_out_of_range_camel_case(self):
        ir_dict = {
            "address": "192.168.0.1",
            "port": "34",
            "version": "5a",
            "community": "public",
            "secret": "secret",
            "securityEngine": "ENGINE",
            "walk_interval": 1850,
            "profiles": "",
            "SmartProfiles": True,
            "delete": False,
        }

        with self.assertRaises(ValueError) as e:
            InventoryRecord(**ir_dict)
        self.assertEqual(
            "version out of range 5a accepted is 1 or 2c or 3",
            e.exception.args[0][0].exc.args[0],
        )

    def test_empty_community_camel_case(self):
        ir_dict = {
            "address": "192.168.0.1",
            "port": "34",
            "version": "3",
            "community": "",
            "secret": "secret",
            "securityEngine": "ENGINE",
            "walk_interval": 1850,
            "profiles": "",
            "SmartProfiles": True,
            "delete": False,
        }

        ir = InventoryRecord(**ir_dict)
        self.assertIsNone(ir.community)

    def test_empty_walk_interval_camel_case(self):
        ir_dict = {
            "address": "192.168.0.1",
            "port": "34",
            "version": "3",
            "community": "public",
            "secret": "secret",
            "securityEngine": "ENGINE",
            "walk_interval": None,
            "profiles": "",
            "SmartProfiles": True,
            "delete": False,
        }

        ir = InventoryRecord(**ir_dict)
        self.assertEqual(42000, ir.walk_interval)

    def test_too_low_walk_interval_camel_case(self):
        ir_dict = {
            "address": "192.168.0.1",
            "port": "34",
            "version": "3",
            "community": "public",
            "secret": "secret",
            "securityEngine": "ENGINE",
            "walk_interval": 20,
            "profiles": "",
            "SmartProfiles": True,
            "delete": False,
        }

        ir = InventoryRecord(**ir_dict)
        self.assertEqual(1800, ir.walk_interval)

    def test_too_high_walk_interval_camel_case(self):
        ir_dict = {
            "address": "192.168.0.1",
            "port": "34",
            "version": "3",
            "community": "public",
            "secret": "secret",
            "securityEngine": "ENGINE",
            "walk_interval": 50000,
            "profiles": "",
            "SmartProfiles": True,
            "delete": False,
        }

        ir = InventoryRecord(**ir_dict)
        self.assertEqual(42000, ir.walk_interval)

    def test_profiles_not_string_camel_case(self):
        ir_dict = {
            "address": "192.168.0.1",
            "port": "34",
            "version": "3",
            "community": "public",
            "secret": "secret",
            "securityEngine": "ENGINE",
            "walk_interval": 1850,
            "profiles": [],
            "SmartProfiles": True,
            "delete": False,
        }

        ir = InventoryRecord(**ir_dict)
        self.assertEqual([], ir.profiles)

    def test_smart_profiles_empty_camel_case(self):
        ir_dict = {
            "address": "192.168.0.1",
            "port": "34",
            "version": "3",
            "community": "public",
            "secret": "secret",
            "securityEngine": "ENGINE",
            "walk_interval": 1850,
            "profiles": "",
            "SmartProfiles": True,
            "delete": False,
        }

        ir = InventoryRecord(**ir_dict)
        self.assertTrue(ir.smart_profiles)

    def test_delete_empty_camel_case(self):
        ir_dict = {
            "address": "192.168.0.1",
            "port": "34",
            "version": "3",
            "community": "public",
            "secret": "secret",
            "securityEngine": "ENGINE",
            "walk_interval": 1850,
            "profiles": "",
            "SmartProfiles": True,
            "delete": "",
        }

        ir = InventoryRecord(**ir_dict)
        self.assertFalse(ir.delete)

    def test_secret_not_specified(self):
        ir_dict = {
            "address": "192.168.0.1",
            "port": "34",
            "version": "3",
            "community": "public",
            "secret": "",
            "securityEngine": "ENGINE",
            "walk_interval": 1850,
            "profiles": "",
            "SmartProfiles": True,
            "delete": "",
        }

        ir = InventoryRecord(**ir_dict)
        self.assertIsNone(ir.secret)

    def test_security_engine_not_specified(self):
        ir_dict = {
            "address": "192.168.0.1",
            "port": "34",
            "version": "3",
            "community": "public",
            "secret": "",
            "securityEngine": "",
            "walk_interval": 1850,
            "profiles": "",
            "SmartProfiles": True,
            "delete": "",
        }

        ir = InventoryRecord(**ir_dict)
        self.assertIsNone(ir.security_engine)

    def test_profiles(self):
        ir_dict = {
            "address": "192.168.0.1",
            "port": "34",
            "version": "3",
            "community": "public",
            "secret": "secret",
            "securityEngine": "ENGINE",
            "walk_interval": 1850,
            "profiles": "generic_switch;new_profiles",
            "SmartProfiles": True,
            "delete": "",
        }

        ir = InventoryRecord(**ir_dict)
        self.assertEqual(["generic_switch", "new_profiles"], ir.profiles)

    def test_smart_profiles_not_specified(self):
        ir_dict = {
            "address": "192.168.0.1",
            "port": "34",
            "version": "3",
            "community": "public",
            "secret": "secret",
            "securityEngine": "ENGINE",
            "walk_interval": 1850,
            "profiles": "generic_switch;new_profiles",
            "SmartProfiles": "",
            "delete": "",
        }

        ir = InventoryRecord(**ir_dict)
        self.assertTrue(ir.smart_profiles)

    def test_asdict_method_without_group(self):
        ir_dict = {
            "address": "192.168.0.1",
            "port": "34",
            "version": "3",
            "community": "public",
            "secret": "secret",
            "securityEngine": "ENGINE",
            "walk_interval": 1850,
            "profiles": "generic_switch;new_profiles",
            "SmartProfiles": "",
            "delete": "",
        }
        expected_dict = {
            "address": "192.168.0.1",
            "port": 34,
            "version": "3",
            "community": "public",
            "secret": "secret",
            "security_engine": "ENGINE",
            "walk_interval": 1850,
            "profiles": ["generic_switch", "new_profiles"],
            "smart_profiles": True,
            "delete": False,
            "group": None,
        }

        ir = InventoryRecord(**ir_dict)
        self.assertEqual(expected_dict, ir.asdict())

    def test_asdict_method(self):
        ir_dict = {
            "address": "192.168.0.1",
            "port": "34",
            "version": "3",
            "community": "public",
            "secret": "secret",
            "securityEngine": "ENGINE",
            "walk_interval": 1850,
            "profiles": "generic_switch;new_profiles",
            "SmartProfiles": "",
            "delete": "",
            "group": "group1",
        }
        expected_dict = {
            "address": "192.168.0.1",
            "port": 34,
            "version": "3",
            "community": "public",
            "secret": "secret",
            "security_engine": "ENGINE",
            "walk_interval": 1850,
            "profiles": ["generic_switch", "new_profiles"],
            "smart_profiles": True,
            "delete": False,
            "group": "group1",
        }

        ir = InventoryRecord(**ir_dict)
        self.assertEqual(expected_dict, ir.asdict())
