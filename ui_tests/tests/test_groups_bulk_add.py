import pytest
from logger.logger import Logger
from pages.groups_page import GroupsPage
from pages.header_page import HeaderPage
from webdriver.webriver_factory import WebDriverFactory

logger = Logger().get_logger()
driver = WebDriverFactory().get_driver()
p_header = HeaderPage()
p_groups = GroupsPage()


@pytest.mark.basic
def test_bulk_add_manual_grid_multiple_devices():
    """
    Test that user is able to add several devices to a group in one go
    using the manual grid in the bulk-add modal,
    check all added devices are displayed on the devices list
    """
    group_name = "test-bulk-manual"
    device_ips = ["10.10.10.1", "10.10.10.2", "10.10.10.3"]
    p_header.switch_to_groups()
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is False
    p_groups.click_add_new_group_button()
    p_groups.set_group_name(group_name)
    p_groups.click_submit_button_for_add_group()
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is True

    p_groups.click_bulk_add_to_group(group_name)
    # the grid opens with one blank row - add two more for the three devices
    p_groups.click_bulk_add_row()
    p_groups.click_bulk_add_row()
    for index, device_ip in enumerate(device_ips):
        p_groups.set_bulk_row_address(index, device_ip)
    p_groups.click_bulk_submit()

    number_of_devices = p_groups.get_number_of_devices_for_group(group_name)
    assert len(device_ips) == number_of_devices
    for device_ip in device_ips:
        is_configured = p_groups.check_if_device_is_configured(device_ip)
        assert is_configured is True

    p_groups.delete_group_from_list(group_name)
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is False


@pytest.mark.basic
def test_bulk_add_paste_address_list_with_shared_config():
    """
    Test that user is able to paste a list of addresses together with a
    shared SNMP config in the bulk-add modal,
    check blank lines, comment lines and duplicate addresses are dropped
    from the preview grid,
    check both remaining devices are saved and displayed on the devices list
    """
    group_name = "test-bulk-paste"
    p_header.switch_to_groups()
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is False
    p_groups.click_add_new_group_button()
    p_groups.set_group_name(group_name)
    p_groups.click_submit_button_for_add_group()
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is True

    p_groups.click_bulk_add_to_group(group_name)
    p_groups.switch_bulk_mode("paste")
    p_groups.set_bulk_shared_version("2c")
    p_groups.set_bulk_shared_community("public")
    p_groups.set_bulk_paste_text("10.20.20.1\n\n# a comment\n10.20.20.2\n10.20.20.1")
    p_groups.click_bulk_expand_addresses()
    number_of_rows = p_groups.get_number_of_bulk_rows()
    assert 2 == number_of_rows

    p_groups.click_bulk_submit()
    number_of_devices = p_groups.get_number_of_devices_for_group(group_name)
    assert 2 == number_of_devices
    assert p_groups.check_if_device_is_configured("10.20.20.1") is True
    assert p_groups.check_if_device_is_configured("10.20.20.2") is True

    p_groups.delete_group_from_list(group_name)
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is False


@pytest.mark.basic
def test_bulk_add_invalid_row_flagged_inline():
    """
    Test that an invalid address in the bulk-add grid is flagged inline
    without being saved,
    check the modal stays open and no device was added to the group
    """
    group_name = "test-bulk-invalid"
    p_header.switch_to_groups()
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is False
    p_groups.click_add_new_group_button()
    p_groups.set_group_name(group_name)
    p_groups.click_submit_button_for_add_group()
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is True

    p_groups.click_bulk_add_to_group(group_name)
    # an address containing a space is invalid
    p_groups.set_bulk_row_address(0, "1.2. 3.4")
    p_groups.click_bulk_submit()
    error_messages = p_groups.get_bulk_row_error_messages()
    assert len(error_messages) > 0
    number_of_devices = p_groups.get_number_of_devices_for_group(group_name)
    assert 0 == number_of_devices
    p_groups.click_bulk_cancel()

    p_groups.delete_group_from_list(group_name)
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is False


@pytest.mark.basic
def test_bulk_add_empty_grid_hint_and_disabled_submit():
    """
    Test that switching to the address-list mode clears the leftover blank
    manual row, showing a hint and disabling submit while the grid is empty,
    check submit is re-enabled once an address is added
    """
    group_name = "test-bulk-empty"
    p_header.switch_to_groups()
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is False
    p_groups.click_add_new_group_button()
    p_groups.set_group_name(group_name)
    p_groups.click_submit_button_for_add_group()
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is True

    p_groups.click_bulk_add_to_group(group_name)
    p_groups.switch_bulk_mode("paste")
    assert p_groups.is_bulk_empty_grid_hint_present() is True
    assert p_groups.is_bulk_submit_enabled() is False

    p_groups.set_bulk_paste_text("10.30.30.1")
    p_groups.click_bulk_expand_addresses()
    assert p_groups.is_bulk_submit_enabled() is True
    p_groups.click_bulk_cancel()

    p_groups.delete_group_from_list(group_name)
    is_on_list = p_groups.check_if_groups_is_on_list(group_name)
    assert is_on_list is False
