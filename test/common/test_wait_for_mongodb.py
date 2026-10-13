import os
from unittest import TestCase
from unittest.mock import MagicMock, patch

from splunk_connect_for_snmp.common.common import wait_for_mongodb_replicaset


class TestWaitForMongoDb(TestCase):
    @patch.dict(
        os.environ,
        {
            "MONGODB_MODE": "replication",
            "MONGO_URI": "mongodb://localhost/?replicaSet=rs0",
        },
    )
    @patch("splunk_connect_for_snmp.common.common.MongoClient")
    def test_closes_client_when_primary_is_not_ready(self, make_client):
        first = MagicMock()
        first.__enter__.return_value.primary = None
        second = MagicMock()
        second.__enter__.return_value.primary = ("localhost", 27017)
        make_client.side_effect = [first, second]

        wait_for_mongodb_replicaset(max_retries=2, retry_interval=0)

        first.__exit__.assert_called_once()
        second.__exit__.assert_called_once()
