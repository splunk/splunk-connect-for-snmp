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
            "SmartProfiles": True,
            "delete": "",
        }

        with self.assertRaises(ValueError) as e:
            InventoryRecord(**ir_dict)
        self.assertEqual("Port out of range 65537", e.exception.args[0][0].exc.args[0])

    def test_version_none(self):
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

    def test_version_out_of_range(self):
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

    def test_empty_community(self):
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

    def test_empty_walk_interval(self):
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

    def test_too_low_walk_interval(self):
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

    def test_too_high_walk_interval(self):
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

    def test_profiles_not_string(self):
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

    def test_smart_profiles_empty(self):
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
        self.assertTrue(ir.SmartProfiles)

    def test_delete_empty(self):
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

    def test_from_json(self):
        ir = InventoryRecord.from_json(
            '{"address": "192.168.0.1", "port": "34", "version": "3", "community": '
            '"public", "secret": "secret", "securityEngine": "ENGINE", "walk_interval": '
            '1850, "profiles": "", "SmartProfiles": true, "delete": ""}'
        )

        self.assertEqual(ir.address, "192.168.0.1")
        self.assertEqual(ir.port, 34)
        self.assertEqual(ir.version, "3")
        self.assertEqual(ir.community, "public")
        self.assertEqual(ir.secret, "secret")
        self.assertEqual(ir.securityEngine, "ENGINE")
        self.assertEqual(ir.walk_interval, 1850)
        self.assertEqual(ir.profiles, [])
        self.assertEqual(ir.SmartProfiles, True)
        self.assertEqual(ir.delete, False)

    def test_to_json(self):
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

        self.assertEqual(
            '{"address": "192.168.0.1", "port": 34, "version": "3", "community": '
            '"public", "secret": "secret", "securityEngine": "ENGINE", "walk_interval": '
            '1850, "profiles": [], "SmartProfiles": true, "delete": false}',
            ir.to_json(),
        )
