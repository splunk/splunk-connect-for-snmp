import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from unittest import TestCase
from unittest.mock import MagicMock, patch

from celery import signals

from splunk_connect_for_snmp.celery_signals_handlers import (
    close_process_mongo_client,
    init_celery_beat_tracing,
    liveness_indicator,
    readiness_indicator,
    rebind_mongo_clients,
)


class TestBeatPolicySignals(TestCase):
    @patch("opentelemetry.instrumentation.celery.CeleryInstrumentor.instrument")
    @patch("opentelemetry.instrumentation.logging.LoggingInstrumentor.instrument")
    def test_beat_registers_policy_without_evaluating_it(self, _m_logging, _m_celery):
        policy_module = ModuleType("splunk_connect_for_snmp.jitter_reconcile")
        policy_module.apply_entry_policy = MagicMock()
        sender = MagicMock()

        with patch.dict(sys.modules, {policy_module.__name__: policy_module}):
            init_celery_beat_tracing(sender=sender)

        self.assertIs(
            sender.app.conf.redbeat_entry_policy, policy_module.apply_entry_policy
        )
        policy_module.apply_entry_policy.assert_not_called()

    def test_worker_signal_import_does_not_load_polling_jitter_settings(self):
        environment = dict(os.environ)
        environment["POLLING_JITTER_WINDOW_SECONDS"] = "invalid"
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys\n"
                "import splunk_connect_for_snmp.celery_signals_handlers\n"
                "assert 'splunk_connect_for_snmp.jitter_reconcile' not in sys.modules\n"
                "assert 'splunk_connect_for_snmp.common.polling_jitter' not in sys.modules",
            ],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)


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
