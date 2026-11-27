from unittest import TestCase
from unittest.mock import MagicMock, mock_open, patch

import pytest

from splunk_connect_for_snmp.common.discovery_record import DiscoveryRecord
from splunk_connect_for_snmp.discovery import loader

FILE_ENTRIES = {
    "from_file": {
        "frequency": 86400,
        "delete_already_discovered": False,
        "network_address": "192.0.2.0/30",
        "version": "2c",
        "community": "public",
        "port": 161,
    }
}


def make_client(flag=None, ui_documents=None):
    """Mongo client whose used_ui_discovery / discovery_ui collections are MagicMocks."""
    database = MagicMock()
    database.used_ui_discovery.find_one.return_value = flag
    database.discovery_ui.find.return_value = list(ui_documents or [])
    database.discovery_ui.find.side_effect = lambda *a, **k: list(ui_documents or [])
    client = MagicMock()
    client.__getitem__.return_value = database
    return client, database


class TestConfigureDiscoveryUiDatabase(TestCase):
    @patch.object(loader, "CONFIG_FROM_MONGO", True)
    def test_first_mongo_run_seeds_collection_and_sets_flag(self):
        client, database = make_client(flag=None, ui_documents=[])

        loader.configure_discovery_ui_database(client, FILE_ENTRIES)

        database.discovery_ui.insert_many.assert_called_once_with(
            [dict(FILE_ENTRIES["from_file"], name="from_file")]
        )
        database.used_ui_discovery.update_one.assert_called_once_with(
            {}, {"$set": {"used_ui_discovery": True}}, upsert=True
        )

    @patch.object(loader, "CONFIG_FROM_MONGO", True)
    def test_seed_does_not_duplicate_entries_created_in_the_ui(self):
        client, database = make_client(flag=None, ui_documents=[{"name": "from_file"}])

        loader.configure_discovery_ui_database(client, FILE_ENTRIES)

        database.discovery_ui.insert_many.assert_not_called()

    @patch.object(loader, "CONFIG_FROM_MONGO", True)
    def test_mongo_entries_are_returned_without_internal_fields(self):
        documents = [
            {"name": "ui_entry", "network_address": "10.0.0.0/24", "port": 161}
        ]
        client, database = make_client(
            flag={"used_ui_discovery": True}, ui_documents=documents
        )

        result = loader.configure_discovery_ui_database(client, FILE_ENTRIES)

        self.assertEqual(
            {"ui_entry": {"network_address": "10.0.0.0/24", "port": 161}}, result
        )
        database.discovery_ui.insert_many.assert_not_called()

    @patch.object(loader, "CONFIG_FROM_MONGO", False)
    def test_disabling_mongo_mode_drops_collection_and_uses_file(self):
        client, database = make_client(flag={"used_ui_discovery": True})

        result = loader.configure_discovery_ui_database(client, FILE_ENTRIES)

        database.discovery_ui.drop.assert_called_once_with()
        database.used_ui_discovery.update_one.assert_called_once_with(
            {}, {"$set": {"used_ui_discovery": False}}, upsert=True
        )
        self.assertEqual(FILE_ENTRIES, result)

    @patch.object(loader, "CONFIG_FROM_MONGO", False)
    def test_file_mode_without_previous_ui_usage_touches_nothing(self):
        client, database = make_client(flag=None)

        result = loader.configure_discovery_ui_database(client, FILE_ENTRIES)

        database.discovery_ui.drop.assert_not_called()
        database.used_ui_discovery.update_one.assert_not_called()
        self.assertEqual(FILE_ENTRIES, result)


class TestLoadWithMongo(TestCase):
    @patch.object(loader, "CONFIG_FROM_MONGO", True)
    @patch.object(loader, "MONGO_URI", None)
    @patch("builtins.open", new_callable=mock_open, read_data="autodiscovery: {}\n")
    def test_mongo_mode_without_mongo_uri_fails(self, _):
        with self.assertRaises(ValueError):
            loader.load()


@pytest.mark.parametrize("port", [0, -1, 65536, "161", True])
def test_port_validator_rejects_invalid_values(port):
    with pytest.raises(ValueError):
        DiscoveryRecord(network_address="10.0.0.0/24", port=port)


@pytest.mark.parametrize("port", [None, 1, 161, 65535])
def test_port_validator_accepts_valid_values(port):
    record = DiscoveryRecord(network_address="10.0.0.0/24", port=port)
    assert record.port == (161 if port is None else port)
