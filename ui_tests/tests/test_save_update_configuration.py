import time

import pytest
from logger.logger import Logger
from pages.groups_page import GroupsPage
from pages.header_page import HeaderPage
from pages.inventory_page import InventoryPage
from pages.profiles_page import ProfilesPage
from pages.yaml_values_reader import YamlValuesReader
from webdriver.webriver_factory import WebDriverFactory

logger = Logger().get_logger()
driver = WebDriverFactory().get_driver()
p_header = HeaderPage()
p_profiles = ProfilesPage()
p_groups = GroupsPage()
p_inventory = InventoryPage()
values_reader = YamlValuesReader()


@pytest.fixture(autouse=True, scope="module")
def setup_and_teardown():
    # clear profiles
    p_header.switch_to_profiles()
    p_profiles.clear_profiles()

    # clear groups
    p_header.switch_to_groups()
    p_groups.clear_groups()

    # clear inventory
    # we should wait for timer expiry to not have temporary records in inventory with delete flag set to true as this will cause test failures
    p_header.switch_to_inventory()
    p_inventory.clear_inventory()
    p_header.apply_changes()
    time_to_upgrade = p_header.get_time_to_upgrade()
    p_header.close_configuration_applied_notification_popup()
    time.sleep(time_to_upgrade + 30)  # wait for upgrade + walk time + polling
    yield
    # teardown here if needed


@pytest.mark.extended
def test_check_that_profile_config_is_stored_upon_applying_configuration():
    """
    Configure profile
    check that profile is stored in yaml file
    edit profile, change freq
    add new profile
    click apply changes once again
    changes stored even when the timer has not yet expired
    """
    profile_name_1 = "store_profile"
    profile_freq_1 = 10
    profile_freq_1_new = 10
    profile_name_2 = "profile_next"
    profile_freq_2 = 77

    p_header.switch_to_profiles()
    p_profiles.click_add_profile_button()
    p_profiles.set_profile_name(profile_name_1)
    p_profiles.set_frequency(profile_freq_1)
    p_profiles.add_varBind("IF-MIB", "ifInErrors", "1")
    p_profiles.click_submit_button()
    time.sleep(1)  # wait for profile to be shown on the list

    # check no profile
    profiles = values_reader.get_scheduler_profiles()
    assert "{}\n" == profiles  # profiles should be empty

    # apply changes
    p_header.apply_changes()
    p_header.close_configuration_applied_notification_popup()

    # check that configuration is stored
    expected_profile_output = f"{profile_name_1}:\n  frequency: {profile_freq_1}\n  varBinds:\n  - ['IF-MIB', 'ifInErrors', '1']\n"
    profiles = values_reader.get_scheduler_profiles()
    assert expected_profile_output == profiles

    # edit profile
    p_profiles.click_edit_profile(profile_name_1)
    p_profiles.set_frequency(profile_freq_1_new)
    p_profiles.click_submit_button()
    # add another profile
    p_profiles.click_add_profile_button()
    p_profiles.set_profile_name(profile_name_2)
    p_profiles.set_frequency(profile_freq_2)
    p_profiles.add_varBind("SNMPv2-MIB", "sysDescr")
    p_profiles.click_submit_button()
    time.sleep(1)  # wait for profile to be shown on the list

    # check that configuration is not changed because it has been not applied
    profiles = values_reader.get_scheduler_profiles()
    assert expected_profile_output == profiles

    # apply changes
    p_header.apply_changes()
    p_header.close_configuration_applied_notification_popup()

    # check that configuration is stored
    expected_profile_output_2 = f"{profile_name_1}:\n  frequency: {profile_freq_1_new}\n  varBinds:\n  - ['IF-MIB', 'ifInErrors', '1']\n{profile_name_2}:\n  frequency: {profile_freq_2}\n  varBinds:\n  - ['SNMPv2-MIB', 'sysDescr']\n"
    profiles = values_reader.get_scheduler_profiles()
    assert expected_profile_output_2 == profiles

    # finalize - clear
    p_profiles.delete_profile_from_list(profile_name_1)
    p_profiles.delete_profile_from_list(profile_name_2)

    # apply changes
    p_header.apply_changes()
    p_header.close_configuration_applied_notification_popup()

    # check no profile
    profiles = values_reader.get_scheduler_profiles()
    assert "{}\n" == profiles  # profiles should be empty


@pytest.mark.extended
def test_check_that_group_config_is_stored_upon_applying_configuration():
    """
    Configure group
    check that group is stored in yaml file
    add device to group
    click apply changes once again
    changes stored even when the timer has not yet expired
    """

    group_name = f"test-group-store"
    device_ip = "11.22.33.44"
    port = 1234
    snmp_version = "2c"
    community_string = "public"
    secret = "secret"
    security_engine = "8000000903000AAAEF536715"
    p_header.switch_to_groups()
    p_groups.click_add_new_group_button()
    p_groups.set_group_name(group_name)
    p_groups.click_submit_button_for_add_group()

    # check no group
    groups = values_reader.get_scheduler_groups()
    assert "{}\n" == groups  # groups should be empty

    # apply changes
    p_header.apply_changes()
    p_header.close_configuration_applied_notification_popup()

    # check that configuration is stored
    expected_group_output = f"{group_name}: []\n"
    groups = values_reader.get_scheduler_groups()
    assert expected_group_output == groups

    # edit group
    p_groups.click_add_device_to_group(group_name)
    p_groups.set_device_ip(device_ip)
    p_groups.set_device_port(port)
    p_groups.set_snmp_version(snmp_version)
    p_groups.set_community_string(community_string)
    p_groups.set_secret(secret)
    p_groups.set_security_engine(security_engine)
    p_groups.click_submit_button_for_add_device()

    # check that configuration is not changed because it has been not applied
    groups = values_reader.get_scheduler_groups()
    assert expected_group_output == groups

    # apply changes
    p_header.apply_changes()
    p_header.close_configuration_applied_notification_popup()

    # check that configuration is stored
    expected_groups_output_2 = f"test-group-store:\n- address: {device_ip}\n  port: {port}\n  version: '{snmp_version}'\n  community: '{community_string}'\n  secret: '{secret}'\n  security_engine: {security_engine}\n"
    groups = values_reader.get_scheduler_groups()
    assert expected_groups_output_2 == groups

    # finalize - clear
    p_groups.delete_group_from_list(group_name)

    # apply changes
    p_header.apply_changes()
    p_header.close_configuration_applied_notification_popup()

    # check no group
    groups = values_reader.get_scheduler_groups()
    assert "{}\n" == groups  # groups should be empty


@pytest.mark.extended
def test_check_that_inventory_config_is_stored_upon_applying_configuration():
    """
    add inventory entry
    check that inventory is stored in yaml file
    remove inventory
    click apply changes once again
    changes stored even when the timer has not yet expired
    """
    inventory_first_row = "address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete"
    host = "88.77.66.55"
    port = "612"
    snmp_version = "2c"
    community = "green"
    walk_interval = "3600"
    smart_profiles = "false"
    profile = "test_profile_1"

    p_header.switch_to_profiles()
    p_profiles.click_add_profile_button()
    p_profiles.set_profile_name(profile)
    p_profiles.add_varBind("IP-MIB", "ifDescr")
    p_profiles.click_submit_button()
    time.sleep(1)  # wait for profile to be shown on the list

    p_header.switch_to_inventory()
    p_inventory.click_add_new_device_group_button()
    p_inventory.set_host_or_group_name(host)
    p_inventory.edit_device_port(port)
    p_inventory.select_snmp_version(snmp_version)
    p_inventory.set_community_string(community)
    p_inventory.set_walk_interval(walk_interval)
    p_inventory.select_profiles([profile])
    p_inventory.set_smart_profiles(smart_profiles)
    p_inventory.click_submit_button_for_add_entry()

    # check no inventory entry
    inventory = values_reader.get_inventory_entries()
    assert inventory_first_row == inventory  # groups should be empty

    # apply changes
    p_header.apply_changes()
    p_header.close_configuration_applied_notification_popup()

    # check that configuration is stored
    expected_inventory_output = f"{inventory_first_row}\n{host},{port},{snmp_version},{community},,,{walk_interval},{profile},f,f"
    inventory = values_reader.get_inventory_entries()
    assert expected_inventory_output == inventory

    # remove inventory
    p_inventory.delete_entry_from_list(host)

    # check that configuration is not changed because it has been not applied
    inventory = values_reader.get_inventory_entries()
    assert expected_inventory_output == inventory

    # apply changes
    p_header.apply_changes()
    p_header.close_configuration_applied_notification_popup()

    # check that configuration is stored
    expected_inventory_output_2 = f"{inventory_first_row}\n{host},{port},{snmp_version},{community},,,{walk_interval},{profile},f,t"
    inventory = values_reader.get_inventory_entries()
    assert expected_inventory_output_2 == inventory

    # finalize - clear
    p_header.switch_to_profiles()
    p_profiles.delete_profile_from_list(profile)

    # apply changes
    p_header.apply_changes()
    p_header.close_configuration_applied_notification_popup()
