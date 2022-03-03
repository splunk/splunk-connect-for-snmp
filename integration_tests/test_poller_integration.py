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

from integration_tests.splunk_test_utils import splunk_single_search

logger = logging.getLogger(__name__)


def test_poller_integration_event(setup_splunk):
    logger.info("Integration test for poller event")
    search_string = """search index="netops" sourcetype="sc4snmp:event" earliest=-5m"""
    result_count, events_count = splunk_single_search(setup_splunk, search_string)
    assert result_count > 0
    assert events_count > 0


def test_poller_integration_metric(setup_splunk):
    logger.info("Integration test for poller metric")
    search_string = "| mcatalog values(metric_name) where index=netmetrics AND metric_name=sc4snmp.* earliest=-5m"
    result_count, metric_count = splunk_single_search(setup_splunk, search_string)
    assert result_count > 0
    assert metric_count > 0


def test_enrich_works_for_IFMIB(setup_splunk):
    logger.info("Integration test for enrichment")
    search_string = """| mpreview index=netmetrics | search sourcetype="sc4snmp:metric" 
    | search "metric_name:sc4snmp.IF-MIB*if" 
    | search "ifDescr" AND "ifAdminStatus" AND "ifOperStatus" AND "ifPhysAddress" AND "ifIndex" """
    result_count, metric_count = splunk_single_search(setup_splunk, search_string)
    assert result_count > 0
    assert metric_count > 0


def test_default_profiles_metrics(setup_splunk):
    logger.info("Integration test for metric profiles")
    search_string_base_if = """| mpreview index=netmetrics | search profiles=BaseIF """
    search_string_base_uptime = (
        """| mpreview index=netmetrics | search profiles=BaseUpTime """
    )
    result_count_if, metric_count_if = splunk_single_search(
        setup_splunk, search_string_base_if
    )
    result_count_uptime, metric_count_uptime = splunk_single_search(
        setup_splunk, search_string_base_uptime
    )
    assert result_count_if > 0
    assert result_count_uptime > 0
    assert metric_count_if > 0
    assert metric_count_uptime > 0


def test_default_profiles_events(setup_splunk):
    logger.info("Integration test for enrichment")
    search_string = """search index=netops | search "IF-MIB.ifAlias" AND "IF-MIB.ifAdminStatus" 
    AND "IF-MIB.ifDescr" AND "IF-MIB.ifName" sourcetype="sc4snmp:event" """
    result_count, metric_count = splunk_single_search(setup_splunk, search_string)
    assert result_count > 0
    assert metric_count > 0
