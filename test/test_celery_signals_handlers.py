from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from splunk_connect_for_snmp.celery_signals_handlers import (
    close_worker_mongo_client,
    liveness_indicator,
    readiness_indicator,
)


class TestIndicators(TestCase):
    @patch.object(Path, "touch")
    def test_liveness_indicator(self, mock_touch):
        liveness_indicator()
        mock_touch.assert_called_once()

    @patch.object(Path, "touch")
    def test_readiness_indicator(self, mock_touch):
        readiness_indicator()
        mock_touch.assert_called_once()


class TestWorkerMongoLifecycle(TestCase):
    @patch("splunk_connect_for_snmp.celery_signals_handlers.close_mongo_client")
    def test_close_worker_mongo_client_delegates_to_mongo_client_module(
        self, m_close_mongo_client
    ):
        close_worker_mongo_client()
        m_close_mongo_client.assert_called_once()
