from unittest import TestCase
from unittest.mock import MagicMock, patch

from splunk_connect_for_snmp.poller import (
    init_celery_beat_tracing,
    init_celery_tracing,
    setup_task_logger,
)


class TestPoller(TestCase):
    @patch("opentelemetry.instrumentation.celery.CeleryInstrumentor.instrument")
    @patch("opentelemetry.instrumentation.logging.LoggingInstrumentor.instrument")
    def test_init_celery_tracing(self, m_instr1, m_instr2):
        init_celery_tracing()
        m_instr1.assert_called()
        m_instr2.assert_called()

    @patch("opentelemetry.instrumentation.celery.CeleryInstrumentor.instrument")
    @patch("opentelemetry.instrumentation.logging.LoggingInstrumentor.instrument")
    def test_init_celery_beat_tracing(self, m_instr1, m_instr2):
        init_celery_beat_tracing()
        m_instr1.assert_called()
        m_instr2.assert_called()

    def test_setup_task_logger(self):
        logger = MagicMock()
        handler1 = MagicMock()
        handler2 = MagicMock()
        logger.handlers = [handler1, handler2]
        setup_task_logger(logger)

        handler1.setFormatter.assert_called()
        handler2.setFormatter.assert_called()
