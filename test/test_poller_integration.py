import logging

from test.splunk_test_utils import splunk_single_search

logger = logging.getLogger(__name__)


def test_poller_integration_event(setup_splunk):
    logger.info(f"Integration test for poller")
    search_string = 'search index="em_logs" sourcetype="sc4snmp:meta" earliest=-1m'
    result_count, events_count = splunk_single_search(setup_splunk, search_string)
    assert result_count > 0
    assert events_count > 0


def test_poller_integration_metric(setup_splunk):
    logger.info(f"Integration test for poller")
    search_string = "| mcatalog values(metric_name)  where index=em_metrics AND metric_name=sc4snmp.*"
    result_count, metric_count = splunk_single_search(setup_splunk, search_string)
    assert result_count > 0
    assert metric_count > 0
