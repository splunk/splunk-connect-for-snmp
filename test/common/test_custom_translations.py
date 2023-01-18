from unittest import TestCase
from unittest.mock import mock_open, patch

from splunk_connect_for_snmp.common.custom_translations import load_custom_translations

mock_config = """customTranslations:
  IF-MIB:
    ifInDiscards: myCustomName1
    ifOutErrors: myCustomName2"""

mock_config_only_profiles = """profiles:
    profile1:"""

mock_config_empty = ""

class TestCustomTranslations(TestCase):
    @patch("builtins.open", new_callable=mock_open, read_data=mock_config)
    def test_load_custom_translations(self, m_open):
        result = load_custom_translations()
        self.assertEqual(
            {
                "IF-MIB": {
                    "ifInDiscards": "myCustomName1",
                    "ifOutErrors": "myCustomName2",
                }
            },
            result,
        )

    @patch("builtins.open", new_callable=mock_open, read_data=mock_config_only_profiles)
    def test_load_custom_translations_only_profiles(self, m_open):
        result = load_custom_translations()
        self.assertIsNone(result)

    @patch("builtins.open", new_callable=mock_open, read_data=mock_config_empty)
    def test_load_custom_translations_empty(self, m_open):
        result = load_custom_translations()
        self.assertIsNone(result)

    @patch("builtins.open", new_callable=mock_open, read_data=mock_config)
    def test_load_custom_translations_no_file(self, m_open):
        m_open.side_effect = FileNotFoundError()
        result = load_custom_translations()
        self.assertIsNone(result)
