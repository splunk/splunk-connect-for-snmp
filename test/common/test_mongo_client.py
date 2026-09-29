from unittest import TestCase
from unittest.mock import MagicMock, patch

from splunk_connect_for_snmp.common import mongo_client


class TestMongoClientLifecycle(TestCase):
    def test_reuses_client_within_process_and_replaces_inherited_client(self):
        with (
            patch.object(mongo_client, "_client", None),
            patch.object(mongo_client, "_client_pid", None),
            patch.object(mongo_client.os, "getpid", return_value=101) as getpid,
            patch.object(
                mongo_client, "MongoClient", side_effect=[MagicMock(), MagicMock()]
            ) as make_client,
        ):
            first = mongo_client.get_mongo_client()
            self.assertIs(first, mongo_client.get_mongo_client())
            make_client.assert_called_once()

            getpid.return_value = 102
            second = mongo_client.get_mongo_client()
            self.assertIsNot(first, second)
            self.assertEqual(2, make_client.call_count)

            mongo_client.close_mongo_client()
            second.close.assert_called_once()
            first.close.assert_not_called()
            mongo_client.close_mongo_client()
            second.close.assert_called_once()
