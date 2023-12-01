import time

import pytest
from logger.logger import Logger
from pages.groups_page import GroupsPage
from pages.header_page import HeaderPage
from pages.inventory_page import InventoryPage
from pages.profiles_page import ProfilesPage
from webdriver.webriver_factory import WebDriverFactory

logger = Logger().get_logger()
driver = WebDriverFactory().get_driver()
p_header = HeaderPage()
p_profiles = ProfilesPage()
p_groups = GroupsPage()
p_inventory = InventoryPage()


@pytest.mark.basic
def test_add_and_remove_inventory_entry():
    """
    Test that user is able to add inventory entry,
    check newly added inventory is displayed on inventory list
    remove inventory entry and check it is not on the list
    """
    host_ip = "1.2.3.4"
    community_string = "public"
    p_header.switch_to_inventory()
    is_on_list = p_inventory.check_if_entry_is_on_list(host_ip)
    assert is_on_list is False
    p_inventory.click_add_new_device_group_button()
    p_inventory.set_host_or_group_name(host_ip)
    p_inventory.set_community_string(community_string)
    p_inventory.click_submit_button_for_add_entry()
    is_on_list = p_inventory.check_if_entry_is_on_list(host_ip)
    assert is_on_list is True
    p_inventory.delete_entry_from_list(host_ip)
    is_on_list = p_inventory.check_if_entry_is_on_list(host_ip)
    assert is_on_list is False


@pytest.mark.basic
def test_add_device_into_inventory_then_change_it():
    """
    Test that user is able to add inventory entry,
    check newly added inventory is displayed on inventory list
    user is able to edit host
    changed host is visible in inventory
    remove inventory entry and check it is not on the list
    """
    host_ip = "1.2.3.4"
    community_string = "public"
    p_header.switch_to_inventory()
    is_on_list = p_inventory.check_if_entry_is_on_list(host_ip)
    assert is_on_list is False
    p_inventory.click_add_new_device_group_button()
    p_inventory.set_host_or_group_name(host_ip)
    p_inventory.set_community_string(community_string)
    p_inventory.click_submit_button_for_add_entry()
    is_on_list = p_inventory.check_if_entry_is_on_list(host_ip)
    assert is_on_list is True
    # change
    new_host_ip = "10.20.30.40"
    p_inventory.click_edit_inventory_entry(host_ip)
    p_inventory.set_host_or_group_name(new_host_ip, True)
    p_inventory.click_submit_button_for_edit_entry()

    expected_notice = "Address or port was edited which resulted in deleting the old device and creating the new one at the end of the list."
    received_notice = p_inventory.get_edit_inventory_notice()
    assert expected_notice == received_notice
    p_inventory.close_edit_inventory_entry()

    is_on_list = p_inventory.check_if_entry_is_on_list(host_ip)
    assert is_on_list is False
    is_on_list = p_inventory.check_if_entry_is_on_list(new_host_ip)
    assert is_on_list is True
    # delete
    p_inventory.delete_entry_from_list(new_host_ip)
    is_on_list = p_inventory.check_if_entry_is_on_list(new_host_ip)
    assert is_on_list is False


@pytest.mark.basic
def test_add_group_into_inventory_entry():
    """
    Test that user is able to add inventory entry,
    check newly added inventory is displayed on inventory list
    user is able to edit host
    changed host is visible in inventory
    remove inventory entry and check it is not on the list
    """
    # add group
    group_name = f"test-group-inventory"
    p_header.switch_to_groups()
    p_groups.click_add_new_group_button()
    p_groups.set_group_name(group_name)
    p_groups.click_submit_button_for_add_group()
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is True

    community_string = "public"
    p_header.switch_to_inventory()
    is_on_list = p_inventory.check_if_entry_is_on_list(group_name)
    assert is_on_list is False
    p_inventory.click_add_new_device_group_button()
    p_inventory.select_group_inventory_type()
    p_inventory.set_host_or_group_name(group_name)
    p_inventory.set_community_string(community_string)
    p_inventory.click_submit_button_for_add_entry()
    is_on_list = p_inventory.check_if_entry_is_on_list(group_name)
    assert is_on_list is True

    # delete
    p_inventory.delete_entry_from_list(group_name)
    is_on_list = p_inventory.check_if_entry_is_on_list(group_name)
    assert is_on_list is False
    p_header.switch_to_groups()
    p_groups.delete_group_from_list(group_name)
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is False


@pytest.mark.basic
def test_try_to_add_device_with_no_data_into_inventory():
    """
    Test that user is not able to add inventory entry with no data
    set host, check community string required
    set community
    check inventory added
    remove inventory entry and check it is not on the list
    """
    host = "1.2.2.1"
    community = "teststring"

    p_header.switch_to_inventory()
    p_inventory.click_add_new_device_group_button()
    p_inventory.click_submit_button_for_add_entry()
    error = p_inventory.get_host_missing_error()
    assert error == "Address or host name is required"
    error = p_inventory.get_community_string_missing_error()
    assert (
        error == "When using SNMP version 1 or 2c, community string must be specified"
    )
    is_on_list = p_inventory.check_if_entry_is_on_list(host)
    assert is_on_list is False

    p_inventory.set_host_or_group_name(host)
    p_inventory.click_submit_button_for_add_entry()
    error = p_inventory.get_host_missing_error()
    assert error is None
    error = p_inventory.get_community_string_missing_error()
    assert (
        error == "When using SNMP version 1 or 2c, community string must be specified"
    )
    is_on_list = p_inventory.check_if_entry_is_on_list(host)
    assert is_on_list is False

    p_inventory.set_community_string(community)
    error = p_inventory.get_community_string_missing_error()
    assert (
        error == "When using SNMP version 1 or 2c, community string must be specified"
    )
    p_inventory.click_submit_button_for_add_entry()
    is_on_list = p_inventory.check_if_entry_is_on_list(host)
    assert is_on_list is True

    # delete
    p_inventory.delete_entry_from_list(host)
    is_on_list = p_inventory.check_if_entry_is_on_list(host)
    assert is_on_list is False


@pytest.mark.basic
def test_setting_min_walk_interval_value_in_inventory():
    """
    Test that user able to set walk interval value
    acceptable valus are in range 1800 - 604800
    test min boundary
    remove inventory entry and check it is not on the list
    """
    host = "3.3.3.3"
    community = "public"

    # min
    p_header.switch_to_inventory()
    p_inventory.click_add_new_device_group_button()

    p_inventory.set_walk_interval("1799")
    p_inventory.click_submit_button_for_add_entry()
    error = p_inventory.get_walk_invalid_value_error()
    assert error == "Walk Interval number must be an integer in range 1800-604800."
    p_inventory.set_walk_interval("1800")

    p_inventory.click_submit_button_for_add_entry()
    error = p_inventory.get_walk_invalid_value_error()
    assert error is None

    # this two fields are set at the end to validate behavior of setting walk interval
    p_inventory.set_host_or_group_name(host)
    p_inventory.set_community_string(community)
    p_inventory.click_submit_button_for_add_entry()
    is_on_list = p_inventory.check_if_entry_is_on_list(host)
    assert is_on_list is True

    # delete
    p_inventory.delete_entry_from_list(host)
    is_on_list = p_inventory.check_if_entry_is_on_list(host)
    assert is_on_list is False


@pytest.mark.basic
def test_setting_max_walk_interval_value_in_inventory():
    """
    Test that user able to set walk interval value
    acceptable valus are in range 1800 - 604800
    test max boundary
    remove inventory entry and check it is not on the list
    """
    host = "4.4.4.4"
    community = "pub_test"

    # min
    p_header.switch_to_inventory()
    p_inventory.click_add_new_device_group_button()

    p_inventory.set_walk_interval("604801")
    p_inventory.click_submit_button_for_add_entry()
    error = p_inventory.get_walk_invalid_value_error()
    assert error == "Walk Interval number must be an integer in range 1800-604800."
    p_inventory.set_walk_interval("604800")
    p_inventory.click_submit_button_for_add_entry()
    error = p_inventory.get_walk_invalid_value_error()
    assert error is None

    # this two fields are set at the end to validate behavior of setting walk interval
    p_inventory.set_host_or_group_name(host)
    p_inventory.set_community_string(community)
    p_inventory.click_submit_button_for_add_entry()
    is_on_list = p_inventory.check_if_entry_is_on_list(host)
    assert is_on_list is True

    # delete
    p_inventory.delete_entry_from_list(host)
    is_on_list = p_inventory.check_if_entry_is_on_list(host)
    assert is_on_list is False


@pytest.mark.basic
def test_try_to_add_device_with_all_available_fields_into_inventory():
    """
    Test that user is not able to add inventory entry all available fields
    then remove inventory entry and check it is not on the list
    """
    host = "1.2.2.1"
    port = "1234"
    snmp_version = "3"
    community = "teststring"
    secret = "test_secret"
    security_engine = "8000000903000AAAEF536715"
    walk_interval = "3600"
    profile_1 = "profile_1"
    profile_2 = "profile_2"
    profiles = [profile_1, profile_2]

    p_header.switch_to_profiles()
    p_profiles.click_add_profile_button()
    p_profiles.set_profile_name(profile_1)
    p_profiles.add_varBind("IP-MIB", "ifDescr")
    p_profiles.click_submit_button()
    time.sleep(1)  # wait for profile to be shown on the list

    p_profiles.click_add_profile_button()
    p_profiles.set_profile_name(profile_2)
    p_profiles.add_varBind("IP-MIB", "ifError")
    p_profiles.click_submit_button()
    time.sleep(1)  # wait for profile to be shown on the list

    p_header.switch_to_inventory()
    p_inventory.click_add_new_device_group_button()
    p_inventory.set_host_or_group_name(host)
    p_inventory.edit_device_port(port)
    p_inventory.select_snmp_version(snmp_version)
    p_inventory.set_community_string(community)
    p_inventory.set_secret(secret)
    p_inventory.set_security_engine(security_engine)
    p_inventory.set_walk_interval(walk_interval)
    p_inventory.select_profiles(profiles)
    p_inventory.set_smart_profiles("true")
    p_inventory.click_submit_button_for_add_entry()
    is_on_list = p_inventory.check_if_entry_is_on_list(host)
    assert is_on_list is True

    # delete
    p_inventory.delete_entry_from_list(host)
    is_on_list = p_inventory.check_if_entry_is_on_list(host)
    assert is_on_list is False
    time.sleep(10)

    p_header.switch_to_profiles()
    p_profiles.delete_profile_from_list(profile_1)
    p_profiles.delete_profile_from_list(profile_2)


@pytest.mark.basic
def test_edit_inventory_entry_with_all_available_fields():
    """
    Test that user is not able to add inventory entry all available fields
    check that user can edit all fields
    check values of edited fields
    then remove inventory entry and check it is not on the list
    """
    host = "99.20.10.10"
    port = "1234"
    snmp_version = "3"
    community = "teststring"
    secret = "test_secret"
    security_engine = "8000000903000AAAEF536715"
    walk_interval = "3600"
    smart_profiles = "false"
    profile_1 = "profile_1_edit"
    profile_2 = "profile_2_edit"

    p_header.switch_to_profiles()
    p_profiles.click_add_profile_button()
    p_profiles.set_profile_name(profile_1)
    p_profiles.add_varBind("IP-MIB", "ifDescr")
    p_profiles.click_submit_button()
    time.sleep(1)  # wait for profile to be shown on the list

    p_profiles.click_add_profile_button()
    p_profiles.set_profile_name(profile_2)
    p_profiles.add_varBind("IP-MIB", "ifError")
    p_profiles.click_submit_button()
    time.sleep(1)  # wait for profile to be shown on the list

    p_header.switch_to_inventory()
    p_inventory.click_add_new_device_group_button()
    p_inventory.set_host_or_group_name(host)
    p_inventory.edit_device_port(port)
    p_inventory.select_snmp_version(snmp_version)
    p_inventory.set_community_string(community)
    p_inventory.set_secret(secret)
    p_inventory.set_security_engine(security_engine)
    p_inventory.set_walk_interval(walk_interval)
    p_inventory.select_profiles([profile_1])
    p_inventory.set_smart_profiles(smart_profiles)
    p_inventory.click_submit_button_for_add_entry()
    is_on_list = p_inventory.check_if_entry_is_on_list(host)
    assert is_on_list is True

    # edit
    new_host = "10.20.30.40"
    new_port = "55555"
    new_snmp_version = "2c"
    new_community = "test_new_community"
    new_secret = "changed_secret"
    new_security_engine = "800000090BC0DD111101"
    new_walk_interval = "10000"
    new_smart_profiles = "true"

    p_inventory.click_edit_inventory_entry(host)
    p_inventory.set_host_or_group_name(new_host, True)
    p_inventory.edit_device_port(new_port)
    p_inventory.select_snmp_version(new_snmp_version)
    p_inventory.set_community_string(new_community, True)
    p_inventory.set_secret(new_secret, True)
    p_inventory.set_security_engine(new_security_engine, True)
    p_inventory.set_walk_interval(new_walk_interval)
    p_inventory.select_profiles([profile_2], True)
    p_inventory.set_smart_profiles(new_smart_profiles)
    p_inventory.click_submit_button_for_add_entry()

    expected_notice = "Address or port was edited which resulted in deleting the old device and creating the new one at the end of the list."
    received_notice = p_inventory.get_edit_inventory_notice()
    assert expected_notice == received_notice
    p_inventory.close_edit_inventory_entry()

    # check
    is_on_list = p_inventory.check_if_entry_is_on_list(host)
    assert is_on_list is False
    is_on_list = p_inventory.check_if_entry_is_on_list(new_host)
    assert is_on_list is True
    received_port = p_inventory.get_port_for_entry(new_host)
    assert new_port == received_port
    received_snmp_version = p_inventory.get_snmp_version_for_entry(new_host)
    assert new_snmp_version == received_snmp_version
    received_community_string = p_inventory.get_community_string_for_entry(new_host)
    assert new_community == received_community_string
    received_secret = p_inventory.get_secret_for_entry(new_host)
    assert new_secret == received_secret
    received_sec_engine = p_inventory.get_security_engine_for_entry(new_host)
    assert new_security_engine == received_sec_engine
    received_walk_interval = p_inventory.get_walk_interval_for_entry(new_host)
    assert new_walk_interval == received_walk_interval
    received_profiles = p_inventory.get_profiles_for_entry(new_host)
    assert profile_2 == received_profiles
    received_smart_profiles = p_inventory.get_smart_profiles_for_entry(new_host)
    assert new_smart_profiles == received_smart_profiles

    # delete
    p_inventory.delete_entry_from_list(new_host)
    is_on_list = p_inventory.check_if_entry_is_on_list(new_host)
    assert is_on_list is False

    p_header.switch_to_profiles()
    p_profiles.delete_profile_from_list(profile_1)
    p_profiles.delete_profile_from_list(profile_2)
