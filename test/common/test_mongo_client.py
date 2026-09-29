from unittest import TestCase
from unittest.mock import MagicMock, patch

from splunk_connect_for_snmp.common import common


def _new_client(*args, **kwargs):
    return MagicMock()


class TestGetMongoClient(TestCase):
    @patch("pymongo.MongoClient")
    def test_reuses_client_within_process(self, m_client):
        first = common.get_mongo_client()
        second = common.get_mongo_client()

        self.assertIs(first, second)
        m_client.assert_called_once()
        self.assertIs(False, m_client.call_args.kwargs["connect"])

    @patch("pymongo.MongoClient", side_effect=_new_client)
    def test_creates_new_client_after_fork(self, m_client):
        with patch("os.getpid", return_value=100):
            parent = common.get_mongo_client()
        with patch("os.getpid", return_value=200):
            child = common.get_mongo_client()
            self.assertIs(child, common.get_mongo_client())

        self.assertIsNot(parent, child)
        self.assertEqual(2, m_client.call_count)
        parent.close.assert_not_called()

    @patch("pymongo.MongoClient", side_effect=_new_client)
    def test_close_closes_own_client(self, _):
        client = common.get_mongo_client()

        common.close_mongo_client()

        client.close.assert_called_once()
        self.assertIsNot(client, common.get_mongo_client())

    @patch("pymongo.MongoClient", side_effect=_new_client)
    def test_close_skips_client_inherited_from_parent(self, _):
        with patch("os.getpid", return_value=100):
            parent = common.get_mongo_client()
        with patch("os.getpid", return_value=200):
            common.close_mongo_client()

        parent.close.assert_not_called()
        self.assertIsNone(common._mongo_client)


class TestPollerRebind(TestCase):
    @patch("pymongo.MongoClient", side_effect=_new_client)
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.__init__", return_value=None)
    def test_rebind_uses_process_client(self, _init, _client):
        from splunk_connect_for_snmp.snmp.manager import Poller

        poller = Poller()
        pre_fork_client = MagicMock()
        poller.mongo_client = pre_fork_client

        poller.rebind_mongo_client()

        shared = common.get_mongo_client()
        self.assertIs(shared, poller.mongo_client)
        self.assertIs(shared, poller.profiles_manager.mongo)
        self.assertIsNot(pre_fork_client, poller.mongo_client)
