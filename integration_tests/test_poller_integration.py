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

from ruamel.yaml.scalarstring import SingleQuotedScalarString as sq

from integration_tests.splunk_test_utils import (
    splunk_single_search,
    update_inventory,
    update_profiles,
    upgrade_helm,
    yaml_escape_list,
)

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


def test_default_profiles_events(setup_splunk):
    logger.info("Integration test for sc4snmp:event")
    search_string = """search index=netops | search "IF-MIB.ifAlias" AND "IF-MIB.ifAdminStatus" 
    AND "IF-MIB.ifDescr" AND "IF-MIB.ifName" sourcetype="sc4snmp:event" """
    result_count, metric_count = splunk_single_search(setup_splunk, search_string)
    assert result_count > 0
    assert metric_count > 0


def test_static_profiles_metrics(request, setup_splunk):
    trap_external_ip = request.config.getoption("trap_external_ip")
    logger.info("Integration test static profile - metrics")
    profile = {
        "generic_switch": {
            "frequency": 5,
            "varBinds": [
                yaml_escape_list(sq("TCP-MIB")),
                yaml_escape_list(sq("IF-MIB"), sq("ifType"), 1),
            ],
        }
    }
    update_profiles(profile)
    update_inventory([f"{trap_external_ip},,2c,public,,,600,generic_switch,,"])
    upgrade_helm(["inventory.yaml", "profiles.yaml"])
    time.sleep(50)
    search_string = """| mpreview index=netmetrics| spath profiles | search profiles=generic_switch 
    | search "TCP-MIB" """
    result_count, metric_count = splunk_single_search(setup_splunk, search_string)
    assert result_count > 0
    assert metric_count > 0


def test_static_profiles_event(setup_splunk):
    search_string = """search index=netops sourcetype="sc4snmp:event" "IF-MIB.ifType" AND NOT "IF-MIB.ifAdminStatus" """
    logger.info("Integration test static profile - events")
    result_count, metric_count = splunk_single_search(setup_splunk, search_string)
    assert result_count > 0
    assert metric_count > 0


def test_add_new_profile_and_reload(request, setup_splunk):
    trap_external_ip = request.config.getoption("trap_external_ip")
    logger.info("Integration test for adding new profile and reloading")
    profile = {
        "new_profile": {"frequency": 7, "varBinds": [yaml_escape_list(sq("IP-MIB"))]},
        "generic_switch": {
            "frequency": 5,
            "varBinds": [yaml_escape_list(sq("UDP-MIB"))],
        },
    }
    update_profiles(profile)
    upgrade_helm(["profiles.yaml"])
    time.sleep(60)
    update_inventory(
        [f"{trap_external_ip},,2c,public,,,600,new_profile;generic_switch,,"]
    )
    upgrade_helm(["inventory.yaml", "profiles.yaml"])
    time.sleep(20)
    search_string = (
        """| mpreview index=netmetrics| spath profiles | search profiles=new_profile """
    )
    result_count, metric_count = splunk_single_search(setup_splunk, search_string)
    assert result_count > 0
    assert metric_count > 0


def test_disable_one_profile_and_reload(request, setup_splunk):
    trap_external_ip = request.config.getoption("trap_external_ip")
    logger.info("Integration test for deleting one profile and reloading")
    profile = {
        "new_profile": {"frequency": 7, "varBinds": [yaml_escape_list(sq("IP-MIB"))]}
    }
    update_profiles(profile)
    update_inventory([f"{trap_external_ip},,2c,public,,,600,new_profile,,"])
    upgrade_helm(["inventory.yaml", "profiles.yaml"])
    time.sleep(70)
    search_string = """| mpreview index=netmetrics| spath profiles | search profiles=generic_switch earliest=-20s """
    result_count, metric_count = splunk_single_search(setup_splunk, search_string)
    assert result_count == 0
    assert metric_count == 0


def test_delete_inventory_line(request, setup_splunk):
    trap_external_ip = request.config.getoption("trap_external_ip")
    logger.info("Integration test for deleting one profile and reloading")
    update_inventory([f"{trap_external_ip},,2c,public,,,600,new_profile,,t"])
    upgrade_helm(["inventory.yaml", "profiles.yaml"])
    time.sleep(40)
    search_string = """| mpreview index=netmetrics earliest=-20s """
    result_count, metric_count = splunk_single_search(setup_splunk, search_string)
    assert result_count == 0
    assert metric_count == 0


def test_smart_profiles_field(request, setup_splunk):
    trap_external_ip = request.config.getoption("trap_external_ip")
    logger.info("Integration test for fields smart profiles")
    profile = {
        "smart_profile_field": {
            "frequency": 3,
            "condition": {
                "type": "field",
                "field": "SNMPv2-MIB.sysDescr",
                "patterns": ["*zeus*"],
            },
            "varBinds": [yaml_escape_list(sq("IP-MIB"), sq("icmpOutDestUnreachs"), 0)],
        }
    }
    update_profiles(profile)
    upgrade_helm(["profiles.yaml"])
    time.sleep(60)
    update_inventory([f"{trap_external_ip},,2c,public,,,600,,t,"])
    upgrade_helm(["inventory.yaml", "profiles.yaml"])
    time.sleep(20)
    search_string = """| mpreview index=netmetrics| spath profiles | search profiles=smart_profile_field """
    result_count, metric_count = splunk_single_search(setup_splunk, search_string)
    assert result_count == 0
    assert metric_count == 0
