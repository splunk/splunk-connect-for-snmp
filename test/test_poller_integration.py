#   ########################################################################
#   Copyright 2021 Splunk Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
#   ########################################################################
import logging

from test.splunk_test_utils import splunk_single_search

logger = logging.getLogger(__name__)


def test_poller_integration_event(setup_splunk):
    logger.info(f"Integration test for poller event")
    search_string = 'search index="em_meta" sourcetype="sc4snmp:meta" earliest=-1m'
    result_count, events_count = splunk_single_search(setup_splunk, search_string)
    assert result_count > 0
    assert events_count > 0


def test_poller_integration_metric(setup_splunk):
    logger.info(f"Integration test for poller metric")
    search_string = "| mcatalog values(metric_name) where index=em_metrics AND metric_name=sc4snmp.* earliest=-1m"
    result_count, metric_count = splunk_single_search(setup_splunk, search_string)
    assert result_count > 0
    assert metric_count > 0
