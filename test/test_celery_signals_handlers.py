from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

from splunk_connect_for_snmp.celery_signals_handlers import (
    close_worker_mongo_client,
    init_worker_mongo_clients,
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
    @patch("celery.current_app")
    def test_init_worker_mongo_clients_initializes_poller_based_tasks(
        self, m_current_app
    ):
        walk_task = MagicMock()
        poll_task = MagicMock()
        # A task with no post-fork bootstrap (e.g. EnrichTask) must not blow up
        # the loop just because it lacks the attribute.
        enrich_task = MagicMock(spec=[])
        m_current_app.tasks = {
            "walk": walk_task,
            "poll": poll_task,
            "enrich": enrich_task,
        }

        init_worker_mongo_clients()

        walk_task._ensure_worker_initialized.assert_called_once()
        poll_task._ensure_worker_initialized.assert_called_once()

    @patch("celery.current_app")
    def test_init_worker_mongo_clients_lets_bootstrap_failures_propagate(
        self, m_current_app
    ):
        # This function itself does no exception handling - a failure here
        # propagates straight out. In the real Celery worker_process_init
        # dispatch, Celery's own Signal.send() will catch and log it rather
        # than let it crash the child; that's a Celery-level behavior, not
        # something this function controls.
        failing_task = MagicMock()
        failing_task._ensure_worker_initialized.side_effect = RuntimeError(
            "Unable to initialize the MIB index"
        )
        m_current_app.tasks = {"walk": failing_task}

        with self.assertRaises(RuntimeError):
            init_worker_mongo_clients()

    @patch("splunk_connect_for_snmp.common.mongo_client.close_mongo_client")
    def test_close_worker_mongo_client_delegates_to_mongo_client_module(
        self, m_close_mongo_client
    ):
        close_worker_mongo_client()

        m_close_mongo_client.assert_called_once()
