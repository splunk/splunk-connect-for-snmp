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
def test_add_and_remove_group():
    """
    Test that user is able to add group,
    check newly added group is displayed on groups list
    remove group and check it is not on the list
    """
    group_name = f"test-group"
    p_header.switch_to_groups()
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is False
    p_groups.click_add_new_group_button()
    p_groups.set_group_name(group_name)
    p_groups.click_submit_button_for_add_group()
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is True
    p_groups.delete_group_from_list(group_name)
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is False


@pytest.mark.basic
def test_change_group_name():
    """
    Test that user is able to add group,
    check that user is able to change group name
    """
    group_name = f"change-name"
    new_group_name = "new-group-name"
    p_header.switch_to_groups()
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is False
    p_groups.click_add_new_group_button()
    p_groups.set_group_name(group_name)
    p_groups.click_submit_button_for_add_group()
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is True
    is_on_list_new = p_groups.check_if_groups_is_on_list(new_group_name)
    assert is_on_list_new is False
    # edit name
    p_groups.edit_group_name(group_name, new_group_name)
    message = p_groups.get_submit_edited_group_name_popup_message()  # common method?
    expected_message = (
        f"{group_name} was also renamed to {new_group_name} in the inventory"
    )
    assert expected_message == message
    p_groups.close_edited_profile_popup()  # common method?
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is False
    is_on_list_new = p_groups.check_if_groups_is_on_list(new_group_name)
    assert is_on_list_new is True

    p_groups.delete_group_from_list(new_group_name)
    is_on_list = p_groups.check_if_groups_is_on_list(new_group_name)
    assert is_on_list is False


@pytest.mark.basic
def test_try_adding_device_to_group_with_no_data():
    """
    Test that user is not able to add device with no data
    check error message
    then click cancel
    check no device on list
    """
    group_name = f"device-with-no-data"
    p_header.switch_to_groups()
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is False
    p_groups.click_add_new_group_button()
    p_groups.set_group_name(group_name)
    p_groups.click_submit_button_for_add_group()
    p_groups.click_add_device_to_group(group_name)
    p_groups.click_submit_button_for_add_device()
    message = p_groups.get_error_message_while_adding_device_with_no_data()
    assert message == "Address or host name is required"
    p_groups.click_cancel_button_for_add_device()
    number_of_devices = p_groups.get_number_of_devices_for_group(group_name)
    assert 0 == number_of_devices
    p_groups.delete_group_from_list(group_name)
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is False


@pytest.mark.basic
def test_add_and_remove_device_into_group():
    """
    Test that user is able to add device into group,
    After adding device into group that group is auto selected
    check added device displayed on devices list
    remove device and check it is not on the list anymore
    """
    group_name = f"test-add-one-device"
    device_ip = "1.2.3.4"
    p_header.switch_to_groups()
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is False
    p_groups.click_add_new_group_button()
    p_groups.set_group_name(group_name)
    p_groups.click_submit_button_for_add_group()
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is True

    p_groups.click_add_device_to_group(group_name)
    p_groups.set_device_ip(device_ip)
    p_groups.click_submit_button_for_add_device()
    number_of_devices = p_groups.get_number_of_devices_for_group(group_name)
    assert 1 == number_of_devices
    is_configured = p_groups.check_if_device_is_configured(device_ip)
    assert is_configured is True
    p_groups.delete_device_from_group(device_ip)
    number_of_devices = p_groups.get_number_of_devices_for_group(group_name)
    assert 0 == number_of_devices
    is_configured = p_groups.check_if_device_is_configured(device_ip)
    assert is_configured is False

    p_groups.delete_group_from_list(group_name)
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is False


@pytest.mark.basic
def test_add_device_with_all_fields():
    """
    Test that user is able to add device into group,
    After adding device into group that group is auto selected
    check added device displayed on devices list
    remove device and check it is not on the list anymore
    """
    group_name = f"test-add-one-device"
    device_ip = "1.2.3.4"
    port = 1234
    snmp_version = "2c"
    community_string = "public"
    secret = "secret"
    security_engine = "8000000903000AAAEF536715"

    p_header.switch_to_groups()
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is False
    p_groups.click_add_new_group_button()
    p_groups.set_group_name(group_name)
    p_groups.click_submit_button_for_add_group()
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is True
    # add device to grp
    p_groups.click_add_device_to_group(group_name)
    p_groups.set_device_ip(device_ip)
    p_groups.set_device_port(port)
    p_groups.set_snmp_version(snmp_version)
    p_groups.set_community_string(community_string)
    p_groups.set_secret(secret)
    p_groups.set_security_engine(security_engine)

    p_groups.click_submit_button_for_add_device()
    is_configured = p_groups.check_if_device_is_configured(device_ip)
    assert is_configured is True

    p_groups.delete_group_from_list(group_name)
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is False


@pytest.mark.basic
def test_edit_device_with_all_fields():
    """
    Test that user is able to add device into group,
    User is able to edit device
    remove device and check it is not on the list anymore
    """
    group_name = f"test-edit-device"
    device_ip = "1.2.3.4"
    port = 1234
    snmp_version = "2c"
    community_string = "public"
    secret = "secret"
    security_engine = "8000000903000AAAEF536715"

    p_header.switch_to_groups()
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is False
    p_groups.click_add_new_group_button()
    p_groups.set_group_name(group_name)
    p_groups.click_submit_button_for_add_group()
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is True
    # add device to grp
    p_groups.click_add_device_to_group(group_name)
    p_groups.set_device_ip(device_ip)
    p_groups.set_device_port(port)
    p_groups.set_snmp_version(snmp_version)
    p_groups.set_community_string(community_string)
    p_groups.set_secret(secret)
    p_groups.set_security_engine(security_engine)
    p_groups.click_submit_button_for_add_device()

    # edit device data
    new_device_ip = "4.3.2.1"
    new_port = 4321
    new_snmp_version = "1"
    new_community_string = "community"
    new_secret = "test"
    new_security_engine = "8000000903000AAAEF511115"

    p_groups.click_edit_device(device_ip)
    p_groups.set_device_ip(new_device_ip, True)
    p_groups.set_device_port(new_port, True)
    p_groups.set_snmp_version(new_snmp_version)
    p_groups.set_community_string(new_community_string, True)
    p_groups.set_secret(new_secret, True)
    p_groups.set_security_engine(new_security_engine, True)
    p_groups.click_submit_button_for_add_device()
    # verify
    is_configured = p_groups.check_if_device_is_configured(device_ip)
    assert is_configured is False
    is_configured = p_groups.check_if_device_is_configured(new_device_ip)
    assert is_configured is True
    port = p_groups.get_device_port(new_device_ip)
    assert int(port) == new_port
    snmp_version_received = p_groups.get_device_snmp_version(new_device_ip)
    assert snmp_version_received == new_snmp_version
    community_string_received = p_groups.get_device_community_string(new_device_ip)
    assert community_string_received == new_community_string
    secret_received = p_groups.get_device_secret(new_device_ip)
    assert secret_received == new_secret
    security_engine_received = p_groups.get_device_security_engine(new_device_ip)
    assert security_engine_received == new_security_engine

    p_groups.delete_group_from_list(group_name)
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is False
