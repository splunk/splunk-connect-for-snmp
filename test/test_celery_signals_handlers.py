from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from splunk_connect_for_snmp.celery_signals_handlers import (
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
