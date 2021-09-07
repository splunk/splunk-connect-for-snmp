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
import time

from test.splunk_test_utils import splunk_single_search

logger = logging.getLogger(__name__)


def test_walk_discovery(setup_splunk):
    logger.info(f"Integration test for poller walk")
    search_string = 'search index="em_meta" sourcetype="sc4snmp:walk"'
    time.sleep(60)
    result_count, events_count = splunk_single_search(setup_splunk, search_string)
    assert result_count > 0
    assert events_count == 96


def test_walk_bulk(setup_splunk):
    logger.info(f"Integration test for poller walk")
    search_string = 'search index="em_meta" sourcetype="sc4snmp:meta" 1.3.6.1.2.1.2'
    result_count, events_count = splunk_single_search(setup_splunk, search_string)
    assert result_count > 0
    assert events_count > 10

