import os
import subprocess
import time

import pytest
from config import config
from logger.logger import Logger
from pages.groups_page import GroupsPage
from pages.header_page import HeaderPage
from pages.inventory_page import InventoryPage
from pages.profiles_page import ProfilesPage
from splunk_search import observe_no_events_from_splunk, wait_for_events_from_splunk
from webdriver.webriver_factory import WebDriverFactory

DEFAULT_PORT = 161
INVENTORY_JOB_NAME = "snmp-splunk-connect-for-snmp-inventory"
INVENTORY_JOB_WAIT_SECONDS = 420
INVENTORY_JOB_POLL_SECONDS = 5
INVENTORY_JOB_LOG_SECONDS = 30

logger = Logger().get_logger()
driver = WebDriverFactory().get_driver()
p_header = HeaderPage()
p_profiles = ProfilesPage()
p_groups = GroupsPage()
p_inventory = InventoryPage()


def apply_changes_when_inventory_job_available():
    """Apply after the previous Job expires so the UI can create a new one.

    The chart retains a completed inventory Job for 300 seconds, while the UI
    backend stops trying to create a replacement after about 90 seconds.
    """
    kubectl = ("microk8s", "kubectl")
    if os.geteuid() != 0:
        kubectl = ("sudo", "-n", *kubectl)
    command = (
        *kubectl,
        "get",
        "job",
        INVENTORY_JOB_NAME,
        "-n",
        "sc4snmp",
        "--ignore-not-found",
        "-o",
        "name",
    )
    deadline = time.monotonic() + INVENTORY_JOB_WAIT_SECONDS
    last_log = 0
    while time.monotonic() < deadline:
        result = subprocess.run(command, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            raise AssertionError(f"Could not check inventory Job: {result.stderr}")
        if not result.stdout.strip():
            p_header.apply_changes()
            p_header.close_configuration_applied_notification_popup()
            return
        if time.monotonic() - last_log >= INVENTORY_JOB_LOG_SECONDS:
            logger.info(
                "Waiting for prior inventory Job to expire: %s", result.stdout.strip()
            )
            last_log = time.monotonic()
        time.sleep(min(INVENTORY_JOB_POLL_SECONDS, max(0, deadline - time.monotonic())))
    raise AssertionError(
        f"Inventory Job {INVENTORY_JOB_NAME} still exists after "
        f"{INVENTORY_JOB_WAIT_SECONDS} seconds"
    )


@pytest.fixture(autouse=True, scope="module")
def setup_and_teardown():
    # clear profiles
    p_header.switch_to_profiles()
    p_profiles.clear_profiles()

    # clear groups
    p_header.switch_to_groups()
    p_groups.clear_groups()

    # clear inventory
    p_header.switch_to_inventory()
    p_inventory.clear_inventory()
    # The first scenario applies this cleared state with its own inventory.
    # Applying here would create a Job that blocks that scenario's next apply.
    yield
    # teardown here if needed


@pytest.mark.extended
def test_applying_changes_for_device_that_does_not_exists(setup):
    """
    Configure device which does not exist
    walk checking, and no polling
    Test that after applying changes:
    walk is scheduled
    no polling is scheduled
    no events received on netops index
    """
    host = "1.2.3.4"
    community = "public"
    profile_name = "splunk_profile_1"
    profile_freq = 10

    p_header.switch_to_profiles()
    p_profiles.click_add_profile_button()
    p_profiles.set_profile_name(profile_name)
    p_profiles.set_frequency(profile_freq)
    p_profiles.add_varbind("IF-MIB", "ifInErrors")
    p_profiles.click_submit_button()

    p_header.switch_to_inventory()
    p_inventory.click_add_new_device_group_button()
    p_inventory.set_host_or_group_name(host)
    p_inventory.select_profiles([profile_name])
    p_inventory.set_community_string(community)
    configured_at = time.time()
    p_inventory.click_submit_button_for_add_entry()
    is_on_list = p_inventory.check_if_entry_is_on_list(host, expected=True)
    assert is_on_list is True

    # apply changes
    apply_changes_when_inventory_job_available()

    # check data in Splunk
    # check walk scheduled
    search_query = f'index={config.LOGS_INDEX} "Sending due task sc4snmp;{host}:{DEFAULT_PORT};walk"'
    events = wait_for_events_from_splunk(
        start_time=str(configured_at),
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
        min_count=1,
    )
    logger.info("Splunk returned %s events for this configuration", len(events))
    assert len(events) == 1
    polling_started_at = time.time()

    # check no profiles polling
    search_query = f'index={config.LOGS_INDEX} "Sending due task sc4snmp;{host}:{DEFAULT_PORT};*;poll"'
    observation_start = time.time()
    observation_end = observation_start + 60
    events = observe_no_events_from_splunk(
        start_time=str(observation_start),
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
        end_time=str(observation_end),
    )
    logger.info("Splunk returned %s events for this configuration", len(events))
    assert len(events) == 0

    # check no events
    search_query = f'index={config.EVENT_INDEX} host="{host}:{DEFAULT_PORT}"'
    events = observe_no_events_from_splunk(
        start_time=str(observation_start),
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
        end_time=str(observation_end),
    )
    logger.info("Splunk returned %s events for this configuration", len(events))
    assert len(events) == 0

    # delete
    p_inventory.delete_entry_from_list(host)
    is_on_list = p_inventory.check_if_entry_is_on_list(host, expected=False)
    assert is_on_list is False
    # clear inventory
    apply_changes_when_inventory_job_available()

    # clear profiles
    p_header.switch_to_profiles()
    p_profiles.delete_profile_from_list(profile_name)


@pytest.mark.extended
def test_setting_group_in_inventory(setup):
    """
    Configure group with device,
    configure smart profiles - disabled,
    configure one standard profile
    apply changes
    check no polling on smart profiles
    check standard profile is working
    """
    group_name = "splk-interaction-grp"
    host = setup["device_simulator"]
    device_endpoint = f"{host}:{DEFAULT_PORT}"
    community = "public"
    profile_name = "standard_profile_12s"
    profile_freq = 12

    p_header.switch_to_profiles()
    p_profiles.click_add_profile_button()
    p_profiles.set_profile_name(profile_name)
    p_profiles.set_frequency(profile_freq)
    p_profiles.add_varbind("IF-MIB", "ifDescr")
    p_profiles.click_submit_button()

    p_header.switch_to_groups()
    p_groups.click_add_new_group_button()
    p_groups.set_group_name(group_name)
    p_groups.click_submit_button_for_add_group()
    p_groups.click_add_device_to_group(group_name)
    p_groups.set_device_ip(host)
    p_groups.click_submit_button_for_add_device()

    p_header.switch_to_inventory()
    p_inventory.click_add_new_device_group_button()
    p_inventory.select_group_inventory_type()
    p_inventory.set_host_or_group_name(group_name)
    p_inventory.select_profiles([profile_name])
    p_inventory.set_community_string(community)
    # Saving can schedule an inventory Job before the Apply button is clicked.
    configured_at = time.time()
    p_inventory.click_submit_button_for_add_entry()
    is_on_list = p_inventory.check_if_entry_is_on_list(group_name, expected=True)
    assert is_on_list is True

    # apply changes
    apply_changes_when_inventory_job_available()

    # check data in Splunk
    # check walk scheduled
    search_query = (
        f'index={config.LOGS_INDEX} "Sending due task sc4snmp;{device_endpoint};walk"'
    )
    events = wait_for_events_from_splunk(
        start_time=str(configured_at),
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
        min_count=1,
    )
    logger.info("Splunk returned %s events for this configuration", len(events))
    assert len(events) == 1
    polling_started_at = time.time()

    # check profiles polling
    search_query = f'index={config.LOGS_INDEX} "Sending due task sc4snmp;{device_endpoint};12;poll"'
    events = wait_for_events_from_splunk(
        start_time=str(polling_started_at),
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
        min_count=2,
    )
    logger.info("Splunk returned %s events for this configuration", len(events))
    assert len(events) > 1

    # checking smart profiles not working
    search_query = f'index={config.LOGS_INDEX} "Sending due task sc4snmp;{device_endpoint};600;poll"'
    observation_start = time.time()
    observation_end = observation_start + 60
    events = observe_no_events_from_splunk(
        start_time=str(observation_start),
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
        end_time=str(observation_end),
    )
    logger.info("Splunk returned %s events for this configuration", len(events))
    assert len(events) == 0

    # checking polling for mandatory profile - 1200 - this should be visible even when smart profiles are disabled
    search_query = f'index={config.LOGS_INDEX} "Sending due task sc4snmp;{device_endpoint};1200;poll"'
    events = wait_for_events_from_splunk(
        start_time=str(configured_at),
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
        min_count=1,
    )
    logger.info("Splunk returned %s events for this configuration", len(events))
    assert len(events) == 1

    # check events received
    search_query = f'index={config.EVENT_INDEX} host="{device_endpoint}"'
    events = wait_for_events_from_splunk(
        start_time=str(polling_started_at),
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
        min_count=2,
    )
    logger.info("Splunk returned %s events for this configuration", len(events))
    assert len(events) > 1

    # delete
    p_inventory.delete_entry_from_list(group_name)
    is_on_list = p_inventory.check_if_entry_is_on_list(group_name, expected=False)
    assert is_on_list is False
    # clear inventory
    apply_changes_when_inventory_job_available()

    # clear groups
    p_header.switch_to_groups()
    p_groups.delete_group_from_list(group_name)

    # clear profiles
    p_header.switch_to_profiles()
    p_profiles.delete_profile_from_list(profile_name)


@pytest.mark.extended
def test_setting_host_in_inventory(setup):
    """
    Configure device, enable smart profiles and two standard profiles, and one base profile
    check smart profiles are working
    check standard profiles are working
    remove one profile freq: 10s
    check profile is not working anymore
    check second profile is still working
    """

    host = setup["device_simulator"]
    device_endpoint = f"{host}:{DEFAULT_PORT}"
    community = "public"
    profile_1_name = "standard_profile_10s"
    profile_1_freq = 10
    profile_2_name = "standard_profile_7s"
    profile_2_freq = 7
    base_profile_name = "base"
    base_profile_freq = 5

    p_header.switch_to_profiles()
    p_profiles.click_add_profile_button()
    p_profiles.set_profile_name(profile_1_name)
    p_profiles.set_frequency(profile_1_freq)
    p_profiles.add_varbind("IF-MIB", "ifDescr")
    p_profiles.click_submit_button()

    p_profiles.click_add_profile_button()
    p_profiles.set_profile_name(profile_2_name)
    p_profiles.set_frequency(profile_2_freq)
    p_profiles.add_varbind("SNMPv2-MIB", "sysName")
    p_profiles.click_submit_button()

    # p_header.switch_to_profiles()
    p_profiles.click_add_profile_button()
    p_profiles.set_profile_name(base_profile_name)
    p_profiles.select_profile_type("base")
    p_profiles.set_frequency(base_profile_freq)
    p_profiles.add_varbind("IF-MIB", "ifDescr")
    p_profiles.click_submit_button()

    p_header.switch_to_inventory()
    p_inventory.click_add_new_device_group_button()
    p_inventory.set_host_or_group_name(host)
    p_inventory.select_profiles([profile_1_name, profile_2_name])
    p_inventory.set_community_string(community)
    p_inventory.set_smart_profiles("true")
    configured_at = time.time()
    p_inventory.click_submit_button_for_add_entry()
    is_on_list = p_inventory.check_if_entry_is_on_list(host, expected=True)
    assert is_on_list is True

    # apply changes
    apply_changes_when_inventory_job_available()

    # check data in Splunk
    # check walk scheduled
    search_query = (
        f'index={config.LOGS_INDEX} "Sending due task sc4snmp;{device_endpoint};walk"'
    )
    events = wait_for_events_from_splunk(
        start_time=str(configured_at),
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
        min_count=1,
    )
    logger.info("Splunk returned %s events for this configuration", len(events))
    assert len(events) == 1
    polling_started_at = time.time()

    # check profiles polling
    search_query = f'index={config.LOGS_INDEX} "Sending due task sc4snmp;{device_endpoint};10;poll"'
    events = wait_for_events_from_splunk(
        start_time=str(polling_started_at),
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
        min_count=2,
    )
    logger.info("Splunk returned %s events for this configuration", len(events))
    assert len(events) > 1

    search_query = (
        f'index={config.LOGS_INDEX} "Sending due task sc4snmp;{device_endpoint};7;poll"'
    )
    events = wait_for_events_from_splunk(
        start_time=str(polling_started_at),
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
        min_count=2,
    )
    logger.info("Splunk returned %s events for this configuration", len(events))
    assert len(events) > 1

    # checking smart/base profiles
    search_query = (
        f'index={config.LOGS_INDEX} "Sending due task sc4snmp;{device_endpoint};5;poll"'
    )
    events = wait_for_events_from_splunk(
        start_time=str(polling_started_at),
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
        min_count=2,
    )
    logger.info("Splunk returned %s events for this configuration", len(events))
    assert len(events) > 1

    # check events received
    search_query = f'index={config.EVENT_INDEX} host="{device_endpoint}"'
    events = wait_for_events_from_splunk(
        start_time=str(polling_started_at),
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
        min_count=2,
    )
    logger.info("Splunk returned %s events for this configuration", len(events))
    assert len(events) > 1

    # remove profiles
    p_inventory.click_edit_inventory_entry(host)
    p_inventory.select_profiles([profile_2_name], True)
    p_inventory.set_smart_profiles("false")
    # p_inventory.set_community_string(new_community, True)
    configured_at = time.time()
    p_inventory.click_submit_button_for_add_entry()
    # apply changes
    apply_changes_when_inventory_job_available()

    # check walk scheduled
    search_query = (
        f'index={config.LOGS_INDEX} "Sending due task sc4snmp;{device_endpoint};walk"'
    )
    events = wait_for_events_from_splunk(
        start_time=str(configured_at),
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
        min_count=1,
    )
    logger.info("Splunk returned %s events for this configuration", len(events))
    assert len(events) == 1
    polling_started_at = time.time()

    # check profiles polling
    search_query = f'index={config.LOGS_INDEX} "Sending due task sc4snmp;{device_endpoint};10;poll"'
    observation_start = time.time()
    observation_end = observation_start + 60
    events = observe_no_events_from_splunk(
        start_time=str(observation_start),
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
        end_time=str(observation_end),
    )
    logger.info("Splunk returned %s events for this configuration", len(events))
    assert len(events) == 0

    search_query = (
        f'index={config.LOGS_INDEX} "Sending due task sc4snmp;{device_endpoint};7;poll"'
    )
    events = wait_for_events_from_splunk(
        start_time=str(polling_started_at),
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
        min_count=2,
    )
    logger.info("Splunk returned %s events for this configuration", len(events))
    assert len(events) > 1

    # checking smart/base profiles - no polling
    search_query = (
        f'index={config.LOGS_INDEX} "Sending due task sc4snmp;{device_endpoint};5;poll"'
    )
    events = observe_no_events_from_splunk(
        start_time=str(observation_start),
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
        end_time=str(observation_end),
    )
    logger.info("Splunk returned %s events for this configuration", len(events))
    assert len(events) == 0

    # check events received
    search_query = f'index={config.EVENT_INDEX} host="{device_endpoint}"'
    events = wait_for_events_from_splunk(
        start_time=str(polling_started_at),
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
        min_count=2,
    )
    logger.info("Splunk returned %s events for this configuration", len(events))
    assert len(events) > 1

    # delete
    p_inventory.delete_entry_from_list(host)
    is_on_list = p_inventory.check_if_entry_is_on_list(host, expected=False)
    assert is_on_list is False
    # clear inventory
    apply_changes_when_inventory_job_available()

    # clear profiles
    p_header.switch_to_profiles()
    p_profiles.delete_profile_from_list(profile_1_name)
    p_profiles.delete_profile_from_list(profile_2_name)
    p_profiles.delete_profile_from_list(base_profile_name)
