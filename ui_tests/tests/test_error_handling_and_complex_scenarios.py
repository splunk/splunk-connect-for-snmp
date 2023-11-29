import time

import pytest
from config import config
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


@pytest.mark.basic
def test_trying_to_configure_profle_with_the_same_name():
    """
    Configure profile
    try to configure profile with the same name again
    check error message
    """
    profile_name = "same_profile"
    profile_freq = 10

    p_header.switch_to_profiles()
    p_profiles.click_add_profile_button()
    p_profiles.set_profile_name(profile_name)
    p_profiles.set_frequency(profile_freq)
    p_profiles.add_varBind("IP-MIB", "ifDescr", 1)
    p_profiles.click_submit_button()
    exist = p_profiles.check_if_profile_is_configured(profile_name)
    assert exist is True

    p_profiles.click_add_profile_button()
    p_profiles.set_profile_name(profile_name)
    p_profiles.set_frequency(profile_freq)
    p_profiles.add_varBind("IP-MIB", "ifDescr", 1)
    p_profiles.click_submit_button()

    message = p_header.get_popup_error_message()
    assert (
        message
        == f"Profile with name {profile_name} already exists. Profile was not added."
    )
    p_header.close_error_popup()
    exist = p_profiles.check_if_profile_is_configured(profile_name)
    assert exist is True

    p_profiles.delete_profile_from_list(profile_name)


@pytest.mark.basic
def test_trying_to_configure_group_with_the_same_name():
    """
    Configure group
    try to configure group with the same name again
    check error message
    """
    group_name = "same_group"

    p_header.switch_to_groups()
    p_groups.click_add_new_group_button()
    p_groups.set_group_name(group_name)
    p_groups.click_submit_button_for_add_group()
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is True

    # try to add same group again
    p_groups.click_add_new_group_button()
    p_groups.set_group_name(group_name)
    p_groups.click_submit_button_for_add_group()
    # check error message
    message = p_header.get_popup_error_message()
    assert (
        message == f"Group with name {group_name} already exists. Group was not added."
    )
    p_header.close_error_popup()

    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is True

    p_groups.delete_group_from_list(group_name)


@pytest.mark.basic
def test_trying_to_add_group_device_which_already_exists():
    """
    Configure group with device
    try to add the same device to the group
    check error message
    """
    group_name = "same_group_device"
    device_ip = "10.20.20.10"
    port = 324
    snmp_version = "2c"
    community_string = "test-device"

    p_header.switch_to_groups()
    p_groups.click_add_new_group_button()
    p_groups.set_group_name(group_name)
    p_groups.click_submit_button_for_add_group()
    # add device to grp
    p_groups.click_add_device_to_group(group_name)
    p_groups.set_device_ip(device_ip)
    p_groups.set_device_port(port)
    p_groups.set_snmp_version(snmp_version)
    p_groups.set_community_string(community_string)
    p_groups.click_submit_button_for_add_device()
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is True

    # try to add same device again
    p_groups.click_add_device_to_group(group_name)
    p_groups.set_device_ip(device_ip)
    p_groups.set_device_port(port)
    p_groups.click_submit_button_for_add_device()
    is_configured = p_groups.check_if_device_is_configured(device_ip)
    assert is_configured is True

    # check error message
    message = p_header.get_popup_error_message()
    assert (
        message
        == f"Host {device_ip}:{port} already exists in group {group_name}. Record was not added."
    )
    p_header.close_error_popup()

    is_configured = p_groups.check_if_device_is_configured(device_ip)
    assert is_configured is True

    p_groups.delete_group_from_list(group_name)


@pytest.mark.basic
def test_trying_to_add_inventory_with_host_which_already_exists():
    """
    Configure inventory with host
    try to add the same host as another inventory entry
    check error message
    """
    host_ip = "100.200.100.200"
    community_string = "test-device"

    p_header.switch_to_inventory()
    p_inventory.click_add_new_device_group_button()
    p_inventory.set_host_or_group_name(host_ip)
    p_inventory.set_community_string(community_string)
    p_inventory.click_submit_button_for_add_entry()
    is_on_list = p_inventory.check_if_entry_is_on_list(host_ip)
    assert is_on_list is True

    # try to add same device again
    p_inventory.click_add_new_device_group_button()
    p_inventory.set_host_or_group_name(host_ip)
    p_inventory.set_community_string("different_string")
    p_inventory.click_submit_button_for_add_entry()

    # check error message
    message = p_header.get_popup_error_message()
    assert (
        message
        == f"Host {host_ip}:{config.DEFAULT_PORT} already exists in the inventory. Record was not added."
    )
    p_header.close_error_popup()
    is_on_list = p_inventory.check_if_entry_is_on_list(host_ip)
    assert is_on_list is True

    p_inventory.delete_entry_from_list(host_ip)


@pytest.mark.basic
def test_trying_to_add_inventory_with_group_which_is_already_added():
    """
    Configure inventory with group
    try to add the same group as another inventory entry
    check error message
    """
    # add group
    group_name = f"test-group-inventory"
    p_header.switch_to_groups()
    p_groups.click_add_new_group_button()
    p_groups.set_group_name(group_name)
    p_groups.click_submit_button_for_add_group()

    community_string = "public"
    p_header.switch_to_inventory()
    p_inventory.click_add_new_device_group_button()
    p_inventory.select_group_inventory_type()
    p_inventory.set_host_or_group_name(group_name)
    p_inventory.set_community_string(community_string)
    p_inventory.click_submit_button_for_add_entry()
    is_on_list = p_inventory.check_if_entry_is_on_list(group_name)
    assert is_on_list is True

    # try to add same device again
    p_inventory.click_add_new_device_group_button()
    p_inventory.select_group_inventory_type()
    p_inventory.set_host_or_group_name(group_name)
    p_inventory.set_community_string("public_test_same_group")
    p_inventory.click_submit_button_for_add_entry()

    # check error message
    message = p_header.get_popup_error_message()
    assert (
        message
        == f"Group {group_name} has already been added to the inventory. Record was not added."
    )
    p_header.close_error_popup()
    is_on_list = p_inventory.check_if_entry_is_on_list(group_name)
    assert is_on_list is True

    # delete
    p_inventory.delete_entry_from_list(group_name)
    p_header.switch_to_groups()
    p_groups.delete_group_from_list(group_name)


@pytest.mark.basic
def test_trying_to_add_inventory_group_with_host_which_is_configured_as_host():
    """
    Configure inventory with group with host
    try to add the inventory entry with the same host which is configured in group
    check error message
    """
    # add group
    group_name = f"test-group-inventory"
    device_ip = "40.50.60.70"
    community_string = "public"

    p_header.switch_to_groups()
    p_groups.click_add_new_group_button()
    p_groups.set_group_name(group_name)
    p_groups.click_submit_button_for_add_group()

    p_groups.click_add_device_to_group(group_name)
    p_groups.set_device_ip(device_ip)
    p_groups.click_submit_button_for_add_device()
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is True

    p_header.switch_to_inventory()
    p_inventory.click_add_new_device_group_button()
    p_inventory.select_group_inventory_type()
    p_inventory.set_host_or_group_name(group_name)
    p_inventory.set_community_string(community_string)
    p_inventory.click_submit_button_for_add_entry()
    is_on_list = p_inventory.check_if_entry_is_on_list(group_name)
    assert is_on_list is True

    # try to add the same host as inventory entry again
    p_inventory.click_add_new_device_group_button()
    p_inventory.set_host_or_group_name(device_ip)
    p_inventory.set_community_string("public_test_same_host")
    p_inventory.click_submit_button_for_add_entry()

    # check error message
    message = p_header.get_popup_error_message()
    assert (
        message
        == f"Host {device_ip}:{config.DEFAULT_PORT} already exists in group {group_name}. Record was not added."
    )
    p_header.close_error_popup()
    is_on_list = p_inventory.check_if_entry_is_on_list(group_name)
    assert is_on_list is True

    # delete
    p_inventory.delete_entry_from_list(group_name)
    p_header.switch_to_groups()
    p_groups.delete_group_from_list(group_name)


@pytest.mark.basic
def test_removing_group_which_is_configured_in_inventory():
    """
    Configure inventory -> add group as inventory entry
    remove group which was added into inventory
    check that upon removing group inventory entry is also removed
    """
    # add group
    group_name = f"test-group-inventory"
    community_string = "public"

    p_header.switch_to_groups()
    p_groups.click_add_new_group_button()
    p_groups.set_group_name(group_name)
    p_groups.click_submit_button_for_add_group()

    p_header.switch_to_inventory()
    p_inventory.click_add_new_device_group_button()
    p_inventory.select_group_inventory_type()
    p_inventory.set_host_or_group_name(group_name)
    p_inventory.set_community_string(community_string)
    p_inventory.click_submit_button_for_add_entry()
    is_on_list = p_inventory.check_if_entry_is_on_list(group_name)
    assert is_on_list is True

    # delete group
    p_header.switch_to_groups()
    # p_groups.delete_group_from_list(group_name)
    p_groups.click_delete_group_button(group_name)
    message = (
        p_groups.get_warning_message_when_removing_group_which_is_configured_in_inventory()
    )
    assert message == "WARNING: This group is configured in the inventory"
    p_groups.confirm_delete()
    p_groups.close_delete_popup()

    # check inventory is also removed
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is False
    p_header.switch_to_inventory()
    is_on_list = p_inventory.check_if_entry_is_on_list(group_name)
    assert is_on_list is False


@pytest.mark.basic
def test_removing_profile_which_is_configured_in_inventory():
    """
    Configure inventory with profile
    remove profile which was added into inventory
    check that upon removing profile, this profile in inventory entry is also removed
    """
    # add group
    profile_name = "removing_profile"
    host = "99.99.99.99"
    community_string = "public"

    p_header.switch_to_profiles()
    p_profiles.click_add_profile_button()
    p_profiles.set_profile_name(profile_name)
    p_profiles.add_varBind("IP-MIB", "ifDescr", 1)
    p_profiles.click_submit_button()
    exist = p_profiles.check_if_profile_is_configured(profile_name)
    assert exist is True

    p_header.switch_to_inventory()
    p_inventory.click_add_new_device_group_button()
    p_inventory.set_host_or_group_name(host)
    p_inventory.select_profiles([profile_name])
    p_inventory.set_community_string(community_string)
    p_inventory.click_submit_button_for_add_entry()
    is_on_list = p_inventory.check_if_entry_is_on_list(host)
    assert is_on_list is True

    # delete profile
    p_header.switch_to_profiles()
    p_profiles.click_delete_profile_button(profile_name)

    message = (
        p_groups.get_warning_message_when_removing_group_which_is_configured_in_inventory()
    )
    assert (
        message
        == "WARNING: This profile is configured in some records in the inventory"
    )
    p_profiles._confirm_delete_profile()
    p_profiles.close_profile_delete_popup()
    exist = p_profiles.check_if_profile_is_configured(profile_name)
    assert exist is False

    # check inventory - no profile
    p_header.switch_to_inventory()
    is_on_list = p_inventory.check_if_entry_is_on_list(host)
    assert is_on_list is True
    received_profiles = p_inventory.get_profiles_for_entry(host)
    assert "" == received_profiles
    # delete inventory entry
    p_inventory.delete_entry_from_list(host)


@pytest.mark.basic
def test_try_to_add_to_inventory_group_which_does_not_exist():
    """
    Configure inventory with group which does not exist
    check error message
    """

    group_name = "does_not_exist"
    community_string = "abcd"
    p_header.switch_to_inventory()

    p_inventory.click_add_new_device_group_button()
    p_inventory.select_group_inventory_type()
    p_inventory.set_host_or_group_name(group_name)
    p_inventory.set_community_string(community_string)
    p_inventory.click_submit_button_for_add_entry()

    # check error message
    message = p_header.get_popup_error_message()
    assert (
        message
        == f"Group {group_name} doesn't exist in the configuration. Record was not added."
    )
    p_header.close_error_popup()
    is_on_list = p_inventory.check_if_entry_is_on_list(group_name)
    assert is_on_list is False


@pytest.mark.basic
def test_trying_to_edit_profile_name_into_profile_name_that_exists():
    """
    Configure two profiles
    try to change one profile to the second
    check error message
    """
    profile_name_1 = "profile_1"
    profile_name_2 = "profile_2"

    p_header.switch_to_profiles()
    p_profiles.click_add_profile_button()
    p_profiles.set_profile_name(profile_name_1)
    p_profiles.add_varBind("IP-MIB", "ifDescr", 1)
    p_profiles.click_submit_button()

    p_profiles.click_add_profile_button()
    p_profiles.set_profile_name(profile_name_2)
    p_profiles.add_varBind("IP-MIB")
    p_profiles.click_submit_button()

    # edit profile name
    p_profiles.click_edit_profile(profile_name_1)
    p_profiles.set_profile_name(profile_name_2)
    p_profiles.click_submit_button()

    message = p_header.get_popup_error_message()
    assert (
        message
        == f"Profile with name {profile_name_2} already exists. Profile was not edited."
    )
    p_header.close_error_popup()
    exist = p_profiles.check_if_profile_is_configured(profile_name_1)
    assert exist is True
    exist = p_profiles.check_if_profile_is_configured(profile_name_2)
    assert exist is True

    p_profiles.delete_profile_from_list(profile_name_1)
    p_profiles.delete_profile_from_list(profile_name_2)


@pytest.mark.basic
def test_trying_to_edit_group_name_into_another_group_name():
    """
    Configure two groups
    try to change one group to the second
    check error message
    """
    group_name_1 = "group_1"
    group_name_2 = "group_2"

    p_header.switch_to_groups()
    p_groups.click_add_new_group_button()
    p_groups.set_group_name(group_name_1)
    p_groups.click_submit_button_for_add_group()

    p_groups.click_add_new_group_button()
    p_groups.set_group_name(group_name_2)
    p_groups.click_submit_button_for_add_group()

    # edit group name
    p_groups.edit_group_name(group_name_1, group_name_2)

    message = p_header.get_popup_error_message()
    assert (
        message
        == f"Group with name {group_name_2} already exists. Group was not edited."
    )
    p_header.close_error_popup()
    is_on_list = p_groups.check_if_groups_is_on_list(group_name_1)
    assert is_on_list is True
    is_on_list = p_groups.check_if_groups_is_on_list(group_name_2)
    assert is_on_list is True

    p_groups.delete_group_from_list(group_name_1)
    p_groups.delete_group_from_list(group_name_2)


@pytest.mark.basic
def test_trying_to_edit_inventory_host_into_host_which_exists():
    """
    Configure two inventory hosts
    try to change one host to the second
    check error message
    """
    host_1 = "11.11.11.11"
    community_1 = "com1"
    host_2 = "22.22.22.22"
    community_2 = "abcs"

    p_header.switch_to_inventory()
    p_inventory.click_add_new_device_group_button()
    p_inventory.set_host_or_group_name(host_1)
    p_inventory.set_community_string(community_1)
    p_inventory.click_submit_button_for_add_entry()

    p_inventory.click_add_new_device_group_button()
    p_inventory.set_host_or_group_name(host_2)
    p_inventory.set_community_string(community_2)
    p_inventory.click_submit_button_for_add_entry()

    # edit inventory host
    p_inventory.click_edit_inventory_entry(host_1)
    p_inventory.set_host_or_group_name(host_2, True)
    p_inventory.click_submit_button_for_add_entry()

    message = p_header.get_popup_error_message()
    assert (
        message
        == f"Host {host_2}:{config.DEFAULT_PORT} already exists in the inventory. Record was not edited."
    )
    p_header.close_error_popup()
    is_on_list = p_inventory.check_if_entry_is_on_list(host_1)
    assert is_on_list is True
    is_on_list = p_inventory.check_if_entry_is_on_list(host_2)
    assert is_on_list is True

    p_inventory.delete_entry_from_list(host_1)
    p_inventory.delete_entry_from_list(host_2)
