import time

import pytest
from config import config
from logger.logger import Logger
from pages.groups_page import GroupsPage
from pages.header_page import HeaderPage
from pages.inventory_page import InventoryPage
from pages.profiles_page import ProfilesPage
from splunk_search import check_events_from_splunk
from webdriver.webriver_factory import WebDriverFactory

logger = Logger().get_logger()
driver = WebDriverFactory().get_driver()
p_header = HeaderPage()
p_profiles = ProfilesPage()
p_groups = GroupsPage()
p_inventory = InventoryPage()


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
    p_header.apply_changes()
    p_header.close_configuration_applied_notification_popup()
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
    p_profiles.add_varBind("IF-MIB", "ifInErrors")
    p_profiles.click_submit_button()
    time.sleep(1)  # wait for profile to be shown on the list

    p_header.switch_to_inventory()
    p_inventory.click_add_new_device_group_button()
    p_inventory.set_host_or_group_name(host)
    p_inventory.select_profiles([profile_name])
    p_inventory.set_community_string(community)
    p_inventory.click_submit_button_for_add_entry()
    is_on_list = p_inventory.check_if_entry_is_on_list(host)
    assert is_on_list is True

    # apply changes
    p_header.apply_changes()
    time_to_upgrade = p_header.get_time_to_upgrade()
    p_header.close_configuration_applied_notification_popup()
    time.sleep(time_to_upgrade + 60)  # wait for upgrade

    # check data in Splunk
    # check walk scheduled
    search_query = (
        "index=" + config.LOGS_INDEX + ' "Sending due task sc4snmp;' + host + ';walk"'
    )
    events = check_events_from_splunk(
        start_time="-3m@m",
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
    )
    logger.info("Splunk received %s events in the last minute", len(events))
    assert len(events) == 1

    # check no profiles polling
    search_query = (
        "index=" + config.LOGS_INDEX + ' "Sending due task sc4snmp;' + host + ';*;poll"'
    )
    events = check_events_from_splunk(
        start_time="-3m@m",
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
    )
    logger.info("Splunk received %s events in the last minute", len(events))
    assert len(events) == 0

    # check no events
    search_query = "index=" + config.EVENT_INDEX + " *"
    events = check_events_from_splunk(
        start_time="-1m@m",
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
    )
    logger.info("Splunk received %s events in the last minute", len(events))
    assert len(events) == 0

    # delete
    p_inventory.delete_entry_from_list(host)
    is_on_list = p_inventory.check_if_entry_is_on_list(host)
    assert is_on_list is False
    # clear inventory
    p_header.apply_changes()
    p_header.close_configuration_applied_notification_popup()

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
    community = "public"
    profile_name = "standard_profile_12s"
    profile_freq = 12

    p_header.switch_to_profiles()
    p_profiles.click_add_profile_button()
    p_profiles.set_profile_name(profile_name)
    p_profiles.set_frequency(profile_freq)
    p_profiles.add_varBind("IF-MIB", "ifDescr")
    p_profiles.click_submit_button()
    time.sleep(1)  # wait for profile to be shown on the list

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
    p_inventory.click_submit_button_for_add_entry()
    is_on_list = p_inventory.check_if_entry_is_on_list(group_name)
    assert is_on_list is True

    # apply changes
    p_header.apply_changes()
    time_to_upgrade = p_header.get_time_to_upgrade()
    p_header.close_configuration_applied_notification_popup()
    time.sleep(time_to_upgrade + 60)  # wait for upgrade + walk time + polling

    # check data in Splunk
    # check walk scheduled
    search_query = (
        "index=" + config.LOGS_INDEX + ' "Sending due task sc4snmp;' + host + ';walk"'
    )
    events = check_events_from_splunk(
        start_time="-2m@m",
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
    )
    logger.info("Splunk received %s events in the last minute", len(events))
    assert len(events) == 1

    # check profiles polling
    search_query = (
        "index="
        + config.LOGS_INDEX
        + ' "Sending due task sc4snmp;'
        + host
        + ';12;poll"'
    )
    events = check_events_from_splunk(
        start_time="-1m@m",
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
    )
    logger.info("Splunk received %s events in the last minute", len(events))
    assert len(events) > 1

    # checking smart profiles not working
    search_query = (
        "index="
        + config.LOGS_INDEX
        + ' "Sending due task sc4snmp;'
        + host
        + ';600;poll"'
    )
    events = check_events_from_splunk(
        start_time="-2m@m",
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
    )
    logger.info("Splunk received %s events in the last minute", len(events))
    assert len(events) == 0

    # checking polling for mandatory profile - 1200 - this should be visible even when smart profiles are disabled
    search_query = (
        "index="
        + config.LOGS_INDEX
        + ' "Sending due task sc4snmp;'
        + host
        + ';1200;poll"'
    )
    events = check_events_from_splunk(
        start_time="-2m@m",
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
    )
    logger.info("Splunk received %s events in the last minute", len(events))
    assert len(events) == 1

    # check events received
    search_query = "index=" + config.EVENT_INDEX + " *"
    events = check_events_from_splunk(
        start_time="-2m@m",
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
    )
    logger.info("Splunk received %s events in the last minute", len(events))
    assert len(events) > 1

    # delete
    p_inventory.delete_entry_from_list(group_name)
    is_on_list = p_inventory.check_if_entry_is_on_list(group_name)
    assert is_on_list is False
    # clear inventory
    p_header.apply_changes()
    p_header.close_configuration_applied_notification_popup()

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
    community = "public"
    new_community = "test1234"
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
    p_profiles.add_varBind("IF-MIB", "ifDescr")
    p_profiles.click_submit_button()

    p_profiles.click_add_profile_button()
    p_profiles.set_profile_name(profile_2_name)
    p_profiles.set_frequency(profile_2_freq)
    p_profiles.add_varBind("SNMPv2-MIB", "sysName")
    p_profiles.click_submit_button()

    p_header.switch_to_profiles()
    p_profiles.click_add_profile_button()
    p_profiles.set_profile_name(base_profile_name)
    p_profiles.select_profile_type("base")
    p_profiles.set_frequency(base_profile_freq)
    p_profiles.add_varBind("IF-MIB", "ifDescr")
    p_profiles.click_submit_button()

    p_header.switch_to_inventory()
    p_inventory.click_add_new_device_group_button()
    p_inventory.set_host_or_group_name(host)
    p_inventory.select_profiles([profile_1_name, profile_2_name])
    p_inventory.set_community_string(community)
    p_inventory.set_smart_profiles("true")
    p_inventory.click_submit_button_for_add_entry()
    is_on_list = p_inventory.check_if_entry_is_on_list(host)
    assert is_on_list is True

    # apply changes
    p_header.apply_changes()
    time_to_upgrade = p_header.get_time_to_upgrade()
    p_header.close_configuration_applied_notification_popup()
    time.sleep(time_to_upgrade + 30)  # wait for upgrade + walk time + polling

    # check data in Splunk
    # check walk scheduled
    search_query = (
        "index=" + config.LOGS_INDEX + ' "Sending due task sc4snmp;' + host + ';walk"'
    )
    events = check_events_from_splunk(
        start_time="-1m@m",
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
    )
    logger.info("Splunk received %s events in the last minute", len(events))
    assert len(events) == 1

    # check profiles polling
    time.sleep(60)  # wait to be sure that profile are being polled
    search_query = (
        "index="
        + config.LOGS_INDEX
        + ' "Sending due task sc4snmp;'
        + host
        + ';10;poll"'
    )
    events = check_events_from_splunk(
        start_time="-1m@m",
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
    )
    logger.info("Splunk received %s events in the last minute", len(events))
    assert len(events) > 1

    search_query = (
        "index=" + config.LOGS_INDEX + ' "Sending due task sc4snmp;' + host + ';7;poll"'
    )
    events = check_events_from_splunk(
        start_time="-1m@m",
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
    )
    logger.info("Splunk received %s events in the last minute", len(events))
    assert len(events) > 1

    # checking smart/base profiles
    search_query = (
        "index=" + config.LOGS_INDEX + ' "Sending due task sc4snmp;' + host + ';5;poll"'
    )
    events = check_events_from_splunk(
        start_time="-1m@m",
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
    )
    logger.info("Splunk received %s events in the last minute", len(events))
    assert len(events) > 1

    # check events received
    search_query = "index=" + config.EVENT_INDEX + " *"
    events = check_events_from_splunk(
        start_time="-1m@m",
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
    )
    logger.info("Splunk received %s events in the last minute", len(events))
    assert len(events) > 1

    # remove profiles
    p_inventory.click_edit_inventory_entry(host)
    p_inventory.select_profiles([profile_2_name], True)
    p_inventory.set_smart_profiles("false")
    # p_inventory.set_community_string(new_community, True)
    p_inventory.click_submit_button_for_add_entry()
    # apply changes
    p_header.apply_changes()
    time_to_upgrade = p_header.get_time_to_upgrade()
    p_header.close_configuration_applied_notification_popup()
    time.sleep(time_to_upgrade + 90)  # wait for upgrade + walk time + polling

    # check walk scheduled
    search_query = (
        "index=" + config.LOGS_INDEX + ' "Sending due task sc4snmp;' + host + ';walk"'
    )
    events = check_events_from_splunk(
        start_time="-2m@m",
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
    )
    logger.info("Splunk received %s events in the last minute", len(events))
    assert len(events) == 1

    # check profiles polling
    time.sleep(60)  # wait to be sure that disabled profile is no more polled
    search_query = (
        "index="
        + config.LOGS_INDEX
        + ' "Sending due task sc4snmp;'
        + host
        + ';10;poll"'
    )
    events = check_events_from_splunk(
        start_time="-1m@m",
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
    )
    logger.info("Splunk received %s events in the last minute", len(events))
    assert len(events) == 0

    search_query = (
        "index=" + config.LOGS_INDEX + ' "Sending due task sc4snmp;' + host + ';7;poll"'
    )
    events = check_events_from_splunk(
        start_time="-1m@m",
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
    )
    logger.info("Splunk received %s events in the last minute", len(events))
    assert len(events) > 1

    # checking smart/base profiles - no polling
    search_query = (
        "index=" + config.LOGS_INDEX + ' "Sending due task sc4snmp;' + host + ';5;poll"'
    )
    events = check_events_from_splunk(
        start_time="-1m@m",
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
    )
    logger.info("Splunk received %s events in the last minute", len(events))
    assert len(events) == 0

    # check events received
    search_query = "index=" + config.EVENT_INDEX + " *"
    events = check_events_from_splunk(
        start_time="-1m@m",
        url=setup["splunkd_url"],
        user=setup["splunk_user"],
        query=["search {}".format(search_query)],
        password=setup["splunk_password"],
    )
    logger.info("Splunk received %s events in the last minute", len(events))
    assert len(events) > 1

    # delete
    p_inventory.delete_entry_from_list(host)
    is_on_list = p_inventory.check_if_entry_is_on_list(host)
    assert is_on_list is False
    # clear inventory
    p_header.apply_changes()
    p_header.close_configuration_applied_notification_popup()

    # clear profiles
    p_header.switch_to_profiles()
    p_profiles.delete_profile_from_list(profile_1_name)
    p_profiles.delete_profile_from_list(profile_2_name)
    p_profiles.delete_profile_from_list(base_profile_name)
