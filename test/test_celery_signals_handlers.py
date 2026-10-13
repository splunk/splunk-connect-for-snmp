from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

from celery import signals

from splunk_connect_for_snmp.celery_signals_handlers import (
    close_process_mongo_client,
    liveness_indicator,
    readiness_indicator,
    rebind_mongo_clients,
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


class TestMongoClientSignals(TestCase):
    @patch("splunk_connect_for_snmp.celery_signals_handlers.current_app")
    def test_rebind_mongo_clients_only_calls_tasks_that_support_it(self, m_app):
        poller_task = MagicMock(spec=["rebind_mongo_client"])
        plain_task = MagicMock(spec=[])
        m_app.tasks = {"poller": poller_task, "plain": plain_task}

        rebind_mongo_clients()

        poller_task.rebind_mongo_client.assert_called_once_with()

    @patch("splunk_connect_for_snmp.celery_signals_handlers.close_mongo_client")
    def test_close_process_mongo_client(self, m_close):
        close_process_mongo_client()

        m_close.assert_called_once_with()

    @patch("splunk_connect_for_snmp.celery_signals_handlers.close_mongo_client")
    def test_parent_mongo_client_closed_before_fork(self, m_close):
        signals.worker_before_create_process.send(sender=MagicMock())

        m_close.assert_called_once_with()
