import os
from unittest import TestCase
from unittest.mock import MagicMock, patch

from splunk_connect_for_snmp.common.mongo_client import (
    close_mongo_client,
    get_mongo_client,
    reset_mongo_client,
)


class TestMongoClient(TestCase):
    def tearDown(self):
        reset_mongo_client()
        super().tearDown()

    @patch("splunk_connect_for_snmp.common.mongo_client.pymongo.MongoClient")
    def test_get_mongo_client_creates_client_from_mongo_uri_env_var(
        self, m_mongo_client
    ):
        with patch.dict(os.environ, {"MONGO_URI": "mongodb://mongo:27017"}):
            client = get_mongo_client()

        m_mongo_client.assert_called_once_with("mongodb://mongo:27017")
        self.assertIs(client, m_mongo_client.return_value)

    @patch("splunk_connect_for_snmp.common.mongo_client.pymongo.MongoClient")
    def test_get_mongo_client_reuses_cached_client_across_calls(self, m_mongo_client):
        first = get_mongo_client()
        second = get_mongo_client()

        m_mongo_client.assert_called_once()
        self.assertIs(first, second)

    @patch("splunk_connect_for_snmp.common.mongo_client.pymongo.MongoClient")
    def test_close_mongo_client_closes_the_cached_client(self, m_mongo_client):
        client = get_mongo_client()

        close_mongo_client()

        client.close.assert_called_once()

    @patch("splunk_connect_for_snmp.common.mongo_client.pymongo.MongoClient")
    def test_close_mongo_client_clears_the_cache_so_a_new_client_is_created_next(
        self, m_mongo_client
    ):
        m_mongo_client.side_effect = [MagicMock(), MagicMock()]

        first = get_mongo_client()
        close_mongo_client()
        second = get_mongo_client()

        self.assertEqual(2, m_mongo_client.call_count)
        self.assertIsNot(first, second)

    @patch("splunk_connect_for_snmp.common.mongo_client.pymongo.MongoClient")
    def test_close_mongo_client_is_a_noop_when_no_client_was_ever_created(
        self, m_mongo_client
    ):
        close_mongo_client()

        m_mongo_client.return_value.close.assert_not_called()

    @patch("splunk_connect_for_snmp.common.mongo_client.pymongo.MongoClient")
    def test_reset_mongo_client_drops_the_reference_without_closing_it(
        self, m_mongo_client
    ):
        m_mongo_client.side_effect = [MagicMock(), MagicMock()]

        client = get_mongo_client()

        reset_mongo_client()

        client.close.assert_not_called()
        second = get_mongo_client()
        self.assertEqual(2, m_mongo_client.call_count)
        self.assertIsNot(client, second)
