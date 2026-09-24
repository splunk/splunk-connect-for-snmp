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
    @patch("splunk_connect_for_snmp.celery_signals_handlers.close_mongo_client")
    def test_close_worker_mongo_client_delegates_to_mongo_client_module(
        self, m_close_mongo_client
    ):
        close_worker_mongo_client()
        m_close_mongo_client.assert_called_once()


class TestEagerWorkerMongoInit(TestCase):
    """
    init_worker_mongo_clients pins the Mongo/MIB bootstrap to worker-startup
    time (worker_process_init fires once per forked child, right after the
    fork) rather than leaving it to whichever task a given worker happens to
    run first - a purely reactive task like trap could otherwise go a long
    time before its first real message, silently leaving its MIB index stale
    relative to what a "restart the worker" operator action is documented to
    achieve.
    """

    @patch("splunk_connect_for_snmp.celery_signals_handlers.current_app")
    def test_calls_ensure_worker_initialized_on_every_task_that_has_it(self, m_app):
        task_with_bootstrap = MagicMock()
        task_without_bootstrap = MagicMock(spec=[])
        m_app.tasks.values.return_value = [
            task_with_bootstrap,
            task_without_bootstrap,
        ]

        init_worker_mongo_clients()

        task_with_bootstrap._ensure_worker_initialized.assert_called_once()

    @patch("splunk_connect_for_snmp.celery_signals_handlers.current_app")
    def test_a_failing_task_bootstrap_is_logged_and_does_not_block_the_rest(
        self, m_app
    ):
        failing_task = MagicMock()
        failing_task.name = "failing-task"
        failing_task._ensure_worker_initialized.side_effect = RuntimeError("boom")
        succeeding_task = MagicMock()
        succeeding_task.name = "succeeding-task"
        m_app.tasks.values.return_value = [failing_task, succeeding_task]

        init_worker_mongo_clients()

        failing_task._ensure_worker_initialized.assert_called_once()
        succeeding_task._ensure_worker_initialized.assert_called_once()
