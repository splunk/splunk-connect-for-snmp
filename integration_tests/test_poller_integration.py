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

import pytest
from ruamel.yaml.scalarstring import SingleQuotedScalarString as sq

from integration_tests.splunk_test_utils import (
    splunk_single_search,
    update_file,
    update_groups,
    update_profiles,
    upgrade_helm,
    yaml_escape_list,
)

logger = logging.getLogger(__name__)


class TestSanity:
    def test_poller_integration_event(self, setup_splunk):
        logger.info("Integration test for poller event")
        search_string = (
            """search index="netops" sourcetype="sc4snmp:event" earliest=-5m"""
        )
        result_count, events_count = splunk_single_search(setup_splunk, search_string)
        assert result_count > 0
        assert events_count > 0

    def test_poller_integration_metric(self, setup_splunk):
        logger.info("Integration test for poller metric")
        search_string = "| mcatalog values(metric_name) where index=netmetrics AND metric_name=sc4snmp.* earliest=-5m"
        result_count, metric_count = splunk_single_search(setup_splunk, search_string)
        assert result_count > 0
        assert metric_count > 0

    def test_enrich_works_for_IFMIB(self, setup_splunk):
        logger.info("Integration test for enrichment")
        search_string = """| mpreview index=netmetrics | search sourcetype="sc4snmp:metric" 
        | search "metric_name:sc4snmp.IF-MIB*if" 
        | search "ifDescr" AND "ifAdminStatus" AND "ifOperStatus" AND "ifPhysAddress" AND "ifIndex" """
        result_count, metric_count = splunk_single_search(setup_splunk, search_string)
        assert result_count > 0
        assert metric_count > 0

    def test_default_profiles_events(self, setup_splunk):
        logger.info("Integration test for sc4snmp:event")
        search_string = """search index=netops | search "IF-MIB.ifAlias" AND "IF-MIB.ifAdminStatus" 
        AND "IF-MIB.ifDescr" AND "IF-MIB.ifName" sourcetype="sc4snmp:event" """
        result_count, metric_count = splunk_single_search(setup_splunk, search_string)
        assert result_count > 0
        assert metric_count > 0


@pytest.fixture(scope="class")
def setup_profile(request):
    trap_external_ip = request.config.getoption("trap_external_ip")
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
    update_file(
        [f"{trap_external_ip},,2c,public,,,600,generic_switch,,"], "inventory.yaml"
    )
    upgrade_helm(["inventory.yaml", "profiles.yaml"])
    time.sleep(30)
    yield
    upgrade_helm([f"{trap_external_ip},,2c,public,,,600,generic_switch,,t"])
    time.sleep(20)


@pytest.mark.usefixtures("setup_profile")
class TestProfiles:
    def test_static_profiles_metrics(self, setup_splunk):
        search_string = """| mpreview index=netmetrics| spath profiles | search profiles=generic_switch 
        | search "TCP-MIB" """
        result_count, metric_count = run_retried_single_search(
            setup_splunk, search_string, 2
        )
        assert result_count > 0
        assert metric_count > 0

    def test_static_profiles_event(self, setup_splunk):
        search_string = """search index=netops sourcetype="sc4snmp:event" "IF-MIB.ifType" AND NOT "IF-MIB.ifAdminStatus" """
        logger.info("Integration test static profile - events")
        result_count, metric_count = run_retried_single_search(
            setup_splunk, search_string, 2
        )
        assert result_count > 0
        assert metric_count > 0


@pytest.fixture(scope="class")
def setup_profiles(request):
    trap_external_ip = request.config.getoption("trap_external_ip")
    profile = {
        "new_profile": {"frequency": 7, "varBinds": [yaml_escape_list(sq("IP-MIB"))]},
        "generic_switch": {
            "frequency": 5,
            "varBinds": [yaml_escape_list(sq("UDP-MIB"))],
        },
    }
    update_profiles(profile)
    # upgrade_helm(["profiles.yaml"])
    # time.sleep(60)
    update_file(
        [f"{trap_external_ip},,2c,public,,,600,new_profile;generic_switch,,"],
        "inventory.yaml",
    )
    upgrade_helm(["inventory.yaml", "profiles.yaml"])
    time.sleep(30)
    yield
    update_file(
        [f"{trap_external_ip},,2c,public,,,600,new_profile;generic_switch,,t"],
        "inventory.yaml",
    )
    upgrade_helm(["inventory.yaml"])
    time.sleep(20)


@pytest.mark.usefixtures("setup_profiles")
class TestProfilesWorkflow:
    def test_add_new_profile_and_reload(self, setup_splunk):
        search_string = """| mpreview index=netmetrics| spath profiles | search profiles=new_profile """
        result_count, metric_count = run_retried_single_search(
            setup_splunk, search_string, 2
        )
        assert result_count > 0
        assert metric_count > 0

    def test_disable_one_profile_and_reload(self, request, setup_splunk):
        trap_external_ip = request.config.getoption("trap_external_ip")
        logger.info("Integration test for deleting one profile and reloading")
        profile = {
            "new_profile": {
                "frequency": 7,
                "varBinds": [yaml_escape_list(sq("IP-MIB"))],
            }
        }
        update_profiles(profile)
        update_file(
            [f"{trap_external_ip},,2c,public,,,600,new_profile,,"], "inventory.yaml"
        )
        upgrade_helm(["inventory.yaml", "profiles.yaml"])
        time.sleep(70)
        search_string = """| mpreview index=netmetrics| spath profiles | search profiles=generic_switch earliest=-20s """
        result_count, metric_count = run_retried_single_search(
            setup_splunk, search_string, 2
        )
        assert result_count == 0
        assert metric_count == 0

    def test_delete_inventory_line(self, request, setup_splunk):
        trap_external_ip = request.config.getoption("trap_external_ip")
        logger.info("Integration test for deleting one profile and reloading")
        update_file(
            [f"{trap_external_ip},,2c,public,,,600,new_profile,,t"], "inventory.yaml"
        )
        upgrade_helm(["inventory.yaml", "profiles.yaml"])
        time.sleep(40)
        search_string = """| mpreview index=netmetrics earliest=-20s """
        result_count, metric_count = run_retried_single_search(
            setup_splunk, search_string, 2
        )
        assert result_count == 0
        assert metric_count == 0


@pytest.fixture(scope="class")
def setup_smart_profiles(request):
    trap_external_ip = request.config.getoption("trap_external_ip")
    logger.info("Integration test for fields smart profiles")
    profile = {
        "smart_profile_field": {
            "frequency": 3,
            "condition": {
                "type": "field",
                "field": "SNMPv2-MIB.sysDescr",
                "patterns": [".*zeus.*"],
            },
            "varBinds": [
                yaml_escape_list(sq("IP-MIB"), sq("icmpOutDestUnreachs"), 0),
                yaml_escape_list(sq("IP-MIB"), sq("icmpOutEchoReps"), 0),
            ],
        }
    }
    update_profiles(profile)
    # upgrade_helm(["inventory.yaml", "profiles.yaml"])
    # time.sleep(60)
    update_file([f"{trap_external_ip},,2c,public,,,600,,t,"], "inventory.yaml")
    upgrade_helm(["inventory.yaml", "profiles.yaml"])
    time.sleep(30)
    yield
    update_file([f"{trap_external_ip},,2c,public,,,600,,t,t"], "inventory.yaml")
    upgrade_helm(["inventory.yaml"])
    time.sleep(20)


@pytest.mark.usefixtures("setup_smart_profiles")
class TestSmartProfiles:
    def test_smart_profiles_field(self, setup_splunk):
        search_string = """| mpreview index=netmetrics| spath profiles | search profiles=smart_profile_field | search icmpOutDestUnreachs """
        result_count, metric_count = run_retried_single_search(
            setup_splunk, search_string, 2
        )
        assert result_count > 0
        assert metric_count > 0

    def test_smart_profiles_custom_translations(self, setup_splunk):
        logger.info(
            "Integration test for fields base smart profiles with custom translations"
        )
        search_string_base = """| mpreview index=netmetrics| spath profiles | search profiles=smart_profile_field | search myCustomName1 """
        result_count, metric_count = run_retried_single_search(
            setup_splunk, search_string_base, 2
        )
        assert result_count > 0
        assert metric_count > 0

    def test_smart_profiles_base(self, setup_splunk):
        logger.info("Integration test for fields base smart profiles")
        search_string_baseIF = (
            """| mpreview index=netmetrics| spath profiles | search profiles=BaseIF """
        )
        search_string_baseUpTime = """| mpreview index=netmetrics| spath profiles | search profiles=BaseUpTime """
        result_count, metric_count = splunk_single_search(
            setup_splunk, search_string_baseIF
        )
        assert result_count > 0
        assert metric_count > 0
        result_count, metric_count = splunk_single_search(
            setup_splunk, search_string_baseUpTime
        )
        assert result_count > 0
        assert metric_count > 0


@pytest.fixture
def setup_modify_profile(request):
    trap_external_ip = request.config.getoption("trap_external_ip")
    profile = {
        "test_modify": {
            "frequency": 5,
            "varBinds": [yaml_escape_list(sq("UDP-MIB"))],
        },
    }
    update_profiles(profile)
    update_file(
        [f"{trap_external_ip},,2c,public,,,600,test_modify,f,"], "inventory.yaml"
    )
    upgrade_helm(["inventory.yaml", "profiles.yaml"])
    time.sleep(30)
    yield
    update_file(
        [f"{trap_external_ip},,2c,public,,,600,test_modify,f,t"], "inventory.yaml"
    )
    upgrade_helm(["inventory.yaml"])
    time.sleep(20)


@pytest.mark.usefixtures("setup_modify_profile")
class TestModifyProfilesFrequency:
    def test_sanity_frequency_field(self, setup_splunk):
        search_string = """| mpreview index=netmetrics earliest=-30s | search profiles=test_modify frequency=5 """
        result_count, metric_count = run_retried_single_search(
            setup_splunk, search_string, 3
        )
        assert result_count > 0
        assert metric_count > 0

    def test_modify_frequency_field(self, request, setup_splunk):
        trap_external_ip = request.config.getoption("trap_external_ip")
        profile = {
            "test_modify": {
                "frequency": 7,
                "varBinds": [yaml_escape_list(sq("UDP-MIB"))],
            },
        }
        update_profiles(profile)
        update_file(
            [f"{trap_external_ip},,2c,public,,,600,test_modify,f,t"], "inventory.yaml"
        )
        upgrade_helm(["inventory.yaml", "profiles.yaml"])
        time.sleep(60)
        update_file(
            [f"{trap_external_ip},,2c,public,,,600,test_modify,f,"], "inventory.yaml"
        )
        upgrade_helm(["inventory.yaml", "profiles.yaml"])
        time.sleep(30)
        search_string = """| mpreview index=netmetrics earliest=-30s | search profiles=test_modify frequency=7 """
        result_count, metric_count = run_retried_single_search(
            setup_splunk, search_string, 8
        )
        assert result_count > 0
        assert metric_count > 0


@pytest.mark.usefixtures("setup_modify_profile")
class TestModifyProfilesVarBinds:
    def test_sanity_varBinds_field(self, setup_splunk):
        search_string = """| mpreview index=netmetrics earliest=-30s | search profiles=test_modify UDP-MIB"""
        result_count, metric_count = run_retried_single_search(
            setup_splunk, search_string, 2
        )
        assert result_count > 0
        assert metric_count > 0

    def test_modify_varBinds_field(self, request, setup_splunk):
        trap_external_ip = request.config.getoption("trap_external_ip")
        profile = {
            "test_modify": {
                "frequency": 7,
                "varBinds": [
                    yaml_escape_list(sq("TCP-MIB")),
                    yaml_escape_list(sq("IP-MIB"), sq("icmpOutDestUnreachs"), 0),
                    yaml_escape_list(sq("UCD-SNMP-MIB"), sq("laIndex")),
                ],
            },
        }
        update_profiles(profile)
        update_file(
            [f"{trap_external_ip},,2c,public,,,600,test_modify,f,t"], "inventory.yaml"
        )
        upgrade_helm(["inventory.yaml", "profiles.yaml"])
        time.sleep(60)
        update_file(
            [f"{trap_external_ip},,2c,public,,,600,test_modify,f,"], "inventory.yaml"
        )
        upgrade_helm(["inventory.yaml", "profiles.yaml"])
        time.sleep(20)
        search_string = """| mpreview index=netmetrics earliest=-15s | search profiles=test_modify TCP-MIB """
        result_count, metric_count = run_retried_single_search(
            setup_splunk, search_string, 2
        )
        assert result_count > 0
        assert metric_count > 0
        search_string = """| mpreview index=netmetrics  earliest=-15s | search profiles=test_modify | search icmpOutDestUnreachs """
        result_count, metric_count = run_retried_single_search(
            setup_splunk, search_string, 2
        )
        assert result_count > 0
        assert metric_count > 0
        search_string = """| mpreview index=netmetrics earliest=-20s | search  laIndex | dedup metric_name:sc4snmp.UCD-SNMP-MIB.laIndex """
        result_count, metric_count = run_retried_single_search(
            setup_splunk, search_string, 2
        )
        assert result_count == 3
        assert metric_count == 3


@pytest.fixture
def setup_small_walk(request):
    trap_external_ip = request.config.getoption("trap_external_ip")
    profile = {
        "walk1": {
            "condition": {"type": "walk"},
            "varBinds": [yaml_escape_list(sq("IP-MIB"))],
        },
    }
    update_profiles(profile)
    update_file([f"{trap_external_ip},,2c,public,,,20,walk1,f,"], "inventory.yaml")
    upgrade_helm(["inventory.yaml", "profiles.yaml"])
    time.sleep(30)
    yield
    update_file([f"{trap_external_ip},,2c,public,,,20,walk1,f,t"], "inventory.yaml")
    upgrade_helm(["inventory.yaml"])
    time.sleep(20)


@pytest.mark.usefixtures("setup_small_walk")
class TestSmallWalk:
    def test_check_if_walk_scope_was_smaller(self, setup_splunk):
        time.sleep(20)
        search_string = (
            """| mpreview index=netmetrics earliest=-20s | search "TCP-MIB" """
        )
        result_count, metric_count = run_retried_single_search(
            setup_splunk, search_string, 1
        )
        assert result_count == 0
        assert metric_count == 0
        search_string = (
            """| mpreview index=netmetrics earliest=-20s | search "IP-MIB" """
        )
        result_count, metric_count = run_retried_single_search(
            setup_splunk, search_string, 2
        )
        assert result_count > 0
        assert metric_count > 0


@pytest.fixture()
def setup_v3_connection(request):
    trap_external_ip = request.config.getoption("trap_external_ip")
    time.sleep(60)
    update_file(
        [f"{trap_external_ip},1161,3,,sv3poller,,20,v3profile,f,"], "inventory.yaml"
    )
    upgrade_helm(["inventory.yaml"])
    time.sleep(30)
    yield
    update_file(
        [f"{trap_external_ip},1161,3,,sv3poller,,20,v3profile,f,t"], "inventory.yaml"
    )
    upgrade_helm(["inventory.yaml"])
    time.sleep(20)


@pytest.mark.usefixtures("setup_v3_connection")
class TestSNMPv3Connection:
    def test_snmpv3_walk(self, setup_splunk):
        time.sleep(100)
        search_string = """| mpreview index=netmetrics | search profiles=v3profile"""
        result_count, metric_count = run_retried_single_search(
            setup_splunk, search_string, 2
        )
        assert result_count > 0
        assert metric_count > 0


@pytest.fixture(scope="class")
def setup_groups(request):
    trap_external_ip = request.config.getoption("trap_external_ip")
    profiles = {
        "single_profile": {
            "frequency": 7,
            "varBinds": [yaml_escape_list(sq("IP-MIB"))],
        },
        "routers_profile": {
            "frequency": 7,
            "varBinds": [yaml_escape_list(sq("IP-MIB"))],
        },
        "switches_profile": {
            "frequency": 7,
            "varBinds": [yaml_escape_list(sq("IP-MIB"))],
        },
    }
    groups = {
        "routers": [
            {"address": trap_external_ip, "port": 1163},
            {"address": trap_external_ip, "port": 1164},
        ],
        "switches": [
            {"address": trap_external_ip},
            {"address": trap_external_ip, "port": 1162},
        ],
    }

    update_profiles(profiles)
    update_groups(groups)
    update_file(
        [
            f"{trap_external_ip},1165,2c,public,,,600,single_profile,,",
            f"routers,,2c,public,,,600,routers_profile,,",
            f"switches,,2c,public,,,600,switches_profile,,",
        ],
        "inventory.yaml",
    )
    upgrade_helm(["inventory.yaml", "profiles.yaml", "groups.yaml"])
    time.sleep(120)
    yield
    update_file(
        [
            f"{trap_external_ip},1165,2c,public,,,600,single_profile,,t",
            f"routers,,2c,public,,,600,routers_profile,,t",
            f"switches,,2c,public,,,600,switches_profile,,t",
        ],
        "inventory.yaml",
    )
    upgrade_helm(["inventory.yaml"])
    time.sleep(100)


@pytest.mark.usefixtures("setup_groups")
class TestGroupsInventory:
    def test_ip_address_inventory(self, setup_splunk):
        time.sleep(20)
        search_string = (
            """| mpreview index=netmetrics | search profiles=single_profile"""
        )
        result_count, metric_count = run_retried_single_search(
            setup_splunk, search_string, 2
        )
        assert result_count > 0
        assert metric_count > 0

    def test_switches_group(self, setup_splunk):
        time.sleep(20)
        search_string = (
            """| mpreview index=netmetrics | search profiles=switches_profile"""
        )
        result_count, metric_count = run_retried_single_search(
            setup_splunk, search_string, 2
        )
        assert result_count > 0
        assert metric_count > 0

    def test_routers_group(self, setup_splunk):
        time.sleep(20)
        search_string = """| mpreview index=netmetrics | search profiles=routers_profile | stats dc(event) by host"""
        result_count, _ = run_retried_single_search(setup_splunk, search_string, 2)
        assert result_count == 2

    def test_edit_routers_group(self, request, setup_splunk):
        trap_external_ip = request.config.getoption("trap_external_ip")
        new_groups = {
            "routers": [{"address": trap_external_ip, "port": 1164}],
            "switches": [
                {"address": trap_external_ip},
                {"address": trap_external_ip, "port": 1162},
            ],
        }
        update_groups(new_groups)
        upgrade_helm(["inventory.yaml", "profiles.yaml", "groups.yaml"])
        time.sleep(30)
        search_string = f"""| mpreview index=netmetrics earliest=-20s | search profiles=routers_profile host="{trap_external_ip}:1163" """
        result_count, metric_count = run_retried_single_search(
            setup_splunk, search_string, 1
        )
        assert result_count == 0
        assert metric_count == 0


@pytest.fixture(scope="class")
def setup_single_ang_group(request):
    trap_external_ip = request.config.getoption("trap_external_ip")
    profiles = {
        "single_profile_1": {
            "frequency": 7,
            "varBinds": [yaml_escape_list(sq("IP-MIB"))],
        },
        "single_profile_2": {
            "frequency": 7,
            "varBinds": [yaml_escape_list(sq("IP-MIB"))],
        },
        "switches_profile": {
            "frequency": 7,
            "varBinds": [yaml_escape_list(sq("IP-MIB"))],
        },
    }
    groups = {
        "switches": [
            {"address": trap_external_ip, "port": 1162},
        ],
    }

    update_profiles(profiles)
    update_groups(groups)
    update_file(
        [
            f"{trap_external_ip},1165,2c,public,,,600,single_profile_1,,",
            f"{trap_external_ip},1162,2c,public,,,600,single_profile_2,,",
            f"switches,,2c,public,,,600,switches_profile,,",
        ],
        "inventory.yaml",
    )
    upgrade_helm(["inventory.yaml", "profiles.yaml", "groups.yaml"])
    time.sleep(120)
    yield
    update_file(
        [
            f"{trap_external_ip},1165,2c,public,,,600,single_profile_1,,t",
            f"{trap_external_ip},1162,2c,public,,,600,single_profile_2,,t",
            f"switches,,2c,public,,,600,switches_profile,,t",
        ],
        "inventory.yaml",
    )
    upgrade_helm(["inventory.yaml"])
    time.sleep(100)


@pytest.mark.usefixtures("setup_single_ang_group")
class TestIgnoreSingleIfInGroup:
    def test_host_from_group(self, request, setup_splunk):
        trap_external_ip = request.config.getoption("trap_external_ip")
        time.sleep(20)
        search_string = f"""| mpreview index=netmetrics | search profiles=switches_profile AND host="{trap_external_ip}:1162" """
        result_count, metric_count = run_retried_single_search(
            setup_splunk, search_string, 2
        )
        assert result_count > 0
        assert metric_count > 0

    def test_inline_host_not_present_in_group(self, request, setup_splunk):
        trap_external_ip = request.config.getoption("trap_external_ip")
        time.sleep(20)
        search_string = f"""| mpreview index=netmetrics | search profiles=single_profile_1 AND host="{trap_external_ip}:1165" """
        result_count, metric_count = run_retried_single_search(
            setup_splunk, search_string, 2
        )
        assert result_count > 0
        assert metric_count > 0

    def test_inline_host_present_in_group(self, request, setup_splunk):
        trap_external_ip = request.config.getoption("trap_external_ip")
        time.sleep(20)
        search_string = f"""| mpreview index=netmetrics | search profiles=single_profile_2 AND host="{trap_external_ip}:1162" """
        result_count, metric_count = run_retried_single_search(
            setup_splunk, search_string, 1
        )
        assert result_count == 0
        assert metric_count == 0


def run_retried_single_search(setup_splunk, search_string, retries):
    for i in range(retries):
        result_count, metric_count = splunk_single_search(setup_splunk, search_string)
        if result_count or metric_count:
            return result_count, metric_count
        logger.info("No results returned from search. Retrying in 2 seconds...")
        time.sleep(2)
    return 0, 0
