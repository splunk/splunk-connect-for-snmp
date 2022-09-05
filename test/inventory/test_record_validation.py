from unittest import TestCase, mock


@mock.patch(
    "splunk_connect_for_snmp.common.collection_manager.ProfilesManager.return_collection"
)
class TestRecordValidation(TestCase):
    def test_disabled_profile(self, return_all_profiles):
        from splunk_connect_for_snmp.inventory.tasks import is_smart_profile_valid

        self.assertFalse(
            is_smart_profile_valid(
                None,
                {"disabled": True, "frequency": 300, "condition": {"type": "base"}},
            )
        )

    def test_frequency_present(self, return_all_profiles):
        from splunk_connect_for_snmp.inventory.tasks import is_smart_profile_valid

        self.assertFalse(is_smart_profile_valid(None, {"condition": {"type": "base"}}))

    def test_condition_present(self, return_all_profiles):
        from splunk_connect_for_snmp.inventory.tasks import is_smart_profile_valid

        self.assertFalse(is_smart_profile_valid(None, {"frequency": 300}))

    def test_condition_type_present(self, return_all_profiles):
        from splunk_connect_for_snmp.inventory.tasks import is_smart_profile_valid

        self.assertFalse(
            is_smart_profile_valid(None, {"frequency": 300, "condition": "asdad"})
        )

    def test_condition_type(self, return_all_profiles):
        from splunk_connect_for_snmp.inventory.tasks import is_smart_profile_valid

        self.assertFalse(
            is_smart_profile_valid(
                None, {"frequency": 300, "condition": {"type": "else"}}
            )
        )

    def test_field_type(self, return_all_profiles):
        from splunk_connect_for_snmp.inventory.tasks import is_smart_profile_valid

        self.assertFalse(
            is_smart_profile_valid(
                None, {"frequency": 300, "condition": {"type": "field"}}
            )
        )

    def test_patterns_present(self, return_all_profiles):
        from splunk_connect_for_snmp.inventory.tasks import is_smart_profile_valid

        self.assertFalse(
            is_smart_profile_valid(
                None,
                {
                    "frequency": 300,
                    "condition": {"type": "field", "field": "sysDescription"},
                },
            )
        )

    def test_patterns_is_list(self, return_all_profiles):
        from splunk_connect_for_snmp.inventory.tasks import is_smart_profile_valid

        self.assertFalse(
            is_smart_profile_valid(
                None,
                {
                    "frequency": 300,
                    "condition": {
                        "type": "field",
                        "field": "sysDescription",
                        "patterns": "ASD",
                    },
                },
            )
        )
        self.assertFalse(
            is_smart_profile_valid(
                None,
                {
                    "frequency": 300,
                    "condition": {
                        "type": "field",
                        "field": "sysDescription",
                        "patterns": {},
                    },
                },
            )
        )

    def test_base_profile_is_valid(self, return_all_profiles):
        from splunk_connect_for_snmp.inventory.tasks import is_smart_profile_valid

        self.assertTrue(
            is_smart_profile_valid(
                None, {"frequency": 300, "condition": {"type": "base"}}
            )
        )

    def test_field_profile_is_valid(self, return_all_profiles):
        from splunk_connect_for_snmp.inventory.tasks import is_smart_profile_valid

        self.assertTrue(
            is_smart_profile_valid(
                None,
                {
                    "frequency": 300,
                    "condition": {
                        "type": "field",
                        "field": "sysDescription",
                        "patterns": ["ASD"],
                    },
                },
            )
        )
