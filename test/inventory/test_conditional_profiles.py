import unittest
from unittest import mock
from unittest.mock import MagicMock


@mock.patch(
    "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.return_collection"
)
class TestCreateQuery(unittest.TestCase):
    def test_single_equals_condition(self, return_all_profiles):
        from splunk_connect_for_snmp.inventory.tasks import create_query

        conditions = [
            {"field": "MIB-FAMILY.field1", "value": "value1", "operation": "equals"}
        ]
        address = "127.0.0.1"
        expected_query = {
            "$and": [
                {"address": address},
                {"group_key_hash": {"$regex": "^MIB-FAMILY"}},
                {"fields.MIB-FAMILY|field1.value": {"$eq": "value1"}},
            ]
        }
        self.assertEqual(create_query(conditions, address), expected_query)

    def test_single_lt_condition(self, return_all_profiles):
        from splunk_connect_for_snmp.inventory.tasks import create_query

        conditions = [{"field": "MIB-FAMILY.field2", "value": "10", "operation": "lt"}]
        address = "127.0.0.1"
        expected_query = {
            "$and": [
                {"address": address},
                {"group_key_hash": {"$regex": "^MIB-FAMILY"}},
                {"fields.MIB-FAMILY|field2.value": {"$lt": 10.0}},
            ]
        }
        self.assertEqual(create_query(conditions, address), expected_query)

    def test_single_gt_condition(self, return_all_profiles):
        from splunk_connect_for_snmp.inventory.tasks import create_query

        conditions = [{"field": "MIB-FAMILY.field3", "value": "20", "operation": "gt"}]
        address = "127.0.0.1"
        expected_query = {
            "$and": [
                {"address": address},
                {"group_key_hash": {"$regex": "^MIB-FAMILY"}},
                {"fields.MIB-FAMILY|field3.value": {"$gt": 20.0}},
            ]
        }
        self.assertEqual(create_query(conditions, address), expected_query)

    def test_single_in_condition(self, return_all_profiles):
        from splunk_connect_for_snmp.inventory.tasks import create_query

        conditions = [
            {"field": "MIB-FAMILY.field4", "value": [1, 2, 3], "operation": "in"}
        ]
        address = "127.0.0.1"
        expected_query = {
            "$and": [
                {"address": address},
                {"group_key_hash": {"$regex": "^MIB-FAMILY"}},
                {"fields.MIB-FAMILY|field4.value": {"$in": [1.0, 2.0, 3.0]}},
            ]
        }
        self.assertEqual(create_query(conditions, address), expected_query)

    def test_multiple_conditions(self, return_all_profiles):
        from splunk_connect_for_snmp.inventory.tasks import create_query

        conditions = [
            {"field": "MIB-FAMILY.field1", "value": "value1", "operation": "equals"},
            {"field": "MIB-FAMILY.field2", "value": "10", "operation": "lt"},
            {"field": "MIB-FAMILY.field3", "value": "20", "operation": "gt"},
            {"field": "MIB-FAMILY.field4", "value": [1, 2, 0], "operation": "in"},
        ]
        address = "127.0.0.1"
        expected_query = {
            "$and": [
                {"address": address},
                {"group_key_hash": {"$regex": "^MIB-FAMILY"}},
                {"fields.MIB-FAMILY|field1.value": {"$eq": "value1"}},
                {"fields.MIB-FAMILY|field2.value": {"$lt": 10.0}},
                {"fields.MIB-FAMILY|field3.value": {"$gt": 20.0}},
                {"fields.MIB-FAMILY|field4.value": {"$in": [1.0, 2.0, 0.0]}},
            ]
        }
        self.assertDictEqual(create_query(conditions, address), expected_query)

    def test_in_conditions_with_many_types(self, return_all_profiles):
        from splunk_connect_for_snmp.inventory.tasks import create_query

        conditions = [
            {"field": "MIB-FAMILY.field4", "value": [1, "2", "up"], "operation": "in"},
        ]
        address = "127.0.0.1"
        expected_query = {
            "$and": [
                {"address": address},
                {"group_key_hash": {"$regex": "^MIB-FAMILY"}},
                {"fields.MIB-FAMILY|field4.value": {"$in": [1.0, 2.0, "up"]}},
            ]
        }
        self.assertDictEqual(create_query(conditions, address), expected_query)

    def test_badly_formatted_lt_gt_condition(self, return_all_profiles):
        from splunk_connect_for_snmp.inventory.tasks import (
            BadlyFormattedFieldError,
            create_query,
        )

        conditions = [
            {"field": "MIB-FAMILY.field4", "value": "up", "operation": "gt"},
        ]
        address = "127.0.0.1"
        with self.assertRaises(BadlyFormattedFieldError) as context:
            create_query(conditions, address)
        self.assertEqual("Value 'up' should be numeric", context.exception.args[0])

    def test_badly_formatted_field(self, return_all_profiles):
        from splunk_connect_for_snmp.inventory.tasks import (
            BadlyFormattedFieldError,
            create_query,
        )

        conditions = [
            {"field": "MIB-FAMILYfield4", "value": 5, "operation": "gt"},
        ]
        address = "127.0.0.1"
        with self.assertRaises(BadlyFormattedFieldError) as context:
            create_query(conditions, address)
        self.assertEqual(
            "Field MIB-FAMILYfield4 is badly formatted", context.exception.args[0]
        )

    @unittest.mock.patch(
        "splunk_connect_for_snmp.inventory.tasks.filter_condition_on_database"
    )
    def test_generate_conditional_profile_with_varbinds(
        self, filter_func, return_all_profiles
    ):
        from splunk_connect_for_snmp.inventory.tasks import generate_conditional_profile

        mongo_client = MagicMock()
        filter_func.return_value = [
            {
                "address": "54.91.99.113",
                "group_key_hash": "IF-MIB::int=4",
                "indexes": [4],
            }
        ]
        profile_name = "test_profile"
        conditional_profile_body = {
            "frequency": 10,
            "conditions": [
                {"field": "MIB-FAMILY.field4", "value": "up", "operation": "equals"},
            ],
            "varBinds": [["MIB-FAMILY", "field"]],
        }
        address = "test_address"
        expected = {
            "test_profile": {"frequency": 10, "varBinds": [["MIB-FAMILY", "field", 4]]}
        }

        result = generate_conditional_profile(
            mongo_client, profile_name, conditional_profile_body, address
        )

        self.assertEqual(result, expected)

    def test_create_profile(self, return_all_profiles):
        from splunk_connect_for_snmp.inventory.tasks import create_profile

        initial_varbinds = [["IF-MIB", "ifDescr"], ["IF-MIB", "ifAlias"]]
        filtered_records = [
            {
                "address": "54.91.99.113",
                "group_key_hash": "IF-MIB::int=4",
                "indexes": [4],
            },
            {
                "address": "54.91.99.113",
                "group_key_hash": "IF-MIB::int=5",
                "indexes": [5],
            },
        ]
        frequency = 60
        result = create_profile(
            "profile_name", frequency, initial_varbinds, filtered_records
        )
        self.assertEqual(
            {
                "profile_name": {
                    "frequency": 60,
                    "varBinds": [
                        ["IF-MIB", "ifDescr", 4],
                        ["IF-MIB", "ifAlias", 4],
                        ["IF-MIB", "ifDescr", 5],
                        ["IF-MIB", "ifAlias", 5],
                    ],
                }
            },
            result,
        )

    def test_create_profile_not_enough_varbinds(self, return_all_profiles):
        from splunk_connect_for_snmp.inventory.tasks import create_profile

        initial_varbinds = [["IF-MIB"]]
        filtered_records = [
            {
                "address": "54.91.99.113",
                "group_key_hash": "IF-MIB::int=4",
                "indexes": [4],
            },
            {
                "address": "54.91.99.113",
                "group_key_hash": "IF-MIB::int=5",
                "indexes": [5],
            },
        ]
        frequency = 60
        result = create_profile(
            "profile_name", frequency, initial_varbinds, filtered_records
        )
        self.assertEqual(
            {
                "profile_name": {
                    "frequency": 60,
                    "varBinds": [],
                }
            },
            result,
        )