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
@pytest.mark.parametrize("profile_type", ["standard", "base"])
def test_add_profile(profile_type):
    """
    Test that user is able to add  profile,
    check newly added profile is displayed on profiles list
    remove profile and check it is not on the list
    """
    profile_name = f"test-profile-{profile_type}"
    p_header.switch_to_profiles()
    exist = p_profiles.check_if_profile_is_configured(profile_name)
    assert exist is False
    p_profiles.click_add_profile_button()
    p_profiles.set_profile_name(profile_name)
    p_profiles.set_frequency(100)
    p_profiles.select_profile_type(profile_type)
    p_profiles.add_varBind("IP-MIB", "ifDescr", 1)
    p_profiles.click_submit_button()
    time.sleep(5)  # wait for profile to be shown on the list
    exist = p_profiles.check_if_profile_is_configured(profile_name)
    assert exist is True
    profile_type_of_profile = p_profiles.get_profile_type_for_profile_entry(
        profile_name
    )
    assert profile_type == profile_type_of_profile
    p_profiles.delete_profile_from_list(profile_name)
    exist = p_profiles.check_if_profile_is_configured(profile_name)
    assert exist is False


@pytest.mark.basic
def test_add_smart_profile():
    """
    Test that user is able to add smart profile,
    check newly added profile is displayed on profiles list
    remove profile and check it is not on the list
    """
    profile_type = "smart"
    profile_name = f"test-profile-{profile_type}"
    p_header.switch_to_profiles()
    time.sleep(5)
    exist = p_profiles.check_if_profile_is_configured(profile_name)
    assert exist is False
    p_profiles.click_add_profile_button()
    p_profiles.set_profile_name(profile_name)
    p_profiles.set_frequency(3600)
    p_profiles.select_profile_type(profile_type)
    p_profiles.set_smart_profile_field("SNMPv2-MIB.sysDescr")
    p_profiles.add_smart_profile_pattern(".*linux.*")
    p_profiles.add_varBind("IP-MIB", "ifDescr", 1)
    p_profiles.click_submit_button()
    time.sleep(5)  # wait for profile to be shown on the list
    exist = p_profiles.check_if_profile_is_configured(profile_name)
    assert exist is True
    profile_type_of_profile = p_profiles.get_profile_type_for_profile_entry(
        profile_name
    )
    assert profile_type == profile_type_of_profile
    p_profiles.delete_profile_from_list(profile_name)
    exist = p_profiles.check_if_profile_is_configured(profile_name)
    assert exist is False


@pytest.mark.basic
def test_add_walk_profile():
    """
    Test that user is able to add walk profile,
    check newly added profile is displayed on profiles list
    remove profile and check it is not on the list
    """
    profile_type = "walk"
    profile_name = f"test-profile-{profile_type}"
    p_header.switch_to_profiles()
    time.sleep(5)
    exist = p_profiles.check_if_profile_is_configured(profile_name)
    assert exist is False
    p_profiles.click_add_profile_button()
    p_profiles.set_profile_name(profile_name)
    p_profiles.select_profile_type(profile_type)
    visible = p_profiles.check_if_frequency_setting_field_is_visible()
    assert visible is False
    p_profiles.add_varBind("IP-MIB", "ifDescr", 1)
    p_profiles.click_submit_button()
    time.sleep(5)  # wait for profile to be shown on the list
    exist = p_profiles.check_if_profile_is_configured(profile_name)
    assert exist is True
    profile_type_of_profile = p_profiles.get_profile_type_for_profile_entry(
        profile_name
    )
    assert profile_type == profile_type_of_profile
    p_profiles.delete_profile_from_list(profile_name)
    exist = p_profiles.check_if_profile_is_configured(profile_name)
    assert exist is False


@pytest.mark.basic
def test_add_conditional_profile():
    """
    Test that user is able to add conditional profile,
    check newly added profile is displayed on profiles list
    remove profile and check it is not on the list
    """
    profile_type = "conditional"
    profile_name = f"test-profile-{profile_type}"
    p_header.switch_to_profiles()
    time.sleep(5)
    exist = p_profiles.check_if_profile_is_configured(profile_name)
    assert exist is False
    p_profiles.click_add_profile_button()
    p_profiles.set_profile_name(profile_name)
    p_profiles.select_profile_type(profile_type)
    p_profiles.add_condition("IF-MIB.ifAdminStatus", "equals", "up")
    p_profiles.add_varBind("IP-MIB", "ifDescr", 1)
    p_profiles.click_submit_button()
    exist = p_profiles.check_if_profile_is_configured(profile_name)
    assert exist is True
    profile_type_of_profile = p_profiles.get_profile_type_for_profile_entry(
        profile_name
    )
    assert profile_type == profile_type_of_profile
    p_profiles.delete_profile_from_list(profile_name)
    exist = p_profiles.check_if_profile_is_configured(profile_name)
    assert exist is False


@pytest.mark.basic
def test_edit_profile():
    """
    Test that user is able to edit profile,
    editing profile name works
    editing frequency works
    editing varBinds works
    """
    profile_type = "standard"
    profile_name = f"test-profile-{profile_type}"
    p_header.switch_to_profiles()
    time.sleep(5)
    exist = p_profiles.check_if_profile_is_configured(profile_name)
    assert exist is False
    p_profiles.click_add_profile_button()
    p_profiles.set_profile_name(profile_name)
    p_profiles.set_frequency(100)
    p_profiles.select_profile_type(profile_type)
    p_profiles.add_varBind("IP-MIB", "ifDescr", 1)
    p_profiles.click_submit_button()
    exist = p_profiles.check_if_profile_is_configured(profile_name)
    assert exist is True
    # edit profile
    new_freq = 45
    new_profile_name = "new_name"
    new_varBind = {"mcomponent": "IP-MIBv2", "mobject": "ifDescr_v2", "mindex": 2}

    p_profiles.click_edit_profile(profile_name)
    p_profiles.set_profile_name(new_profile_name)
    p_profiles.set_frequency(new_freq)
    p_profiles.edit_varBind(
        new_varBind["mcomponent"], new_varBind["mobject"], new_varBind["mindex"]
    )
    p_profiles.click_submit_button()

    # verify notice : If {pname} was used in some records in the inventory, it was updated to {new_pname}
    received = p_profiles.get_submit_edited_profile_text()
    expected = f"If {profile_name} was used in some records in the inventory, it was updated to {new_profile_name}"
    assert expected == received
    p_profiles.close_edited_profile_popup()
    # check edited fields
    # name
    exist = p_profiles.check_if_profile_is_configured(profile_name)
    assert exist is False
    exist = p_profiles.check_if_profile_is_configured(new_profile_name)
    assert exist is True
    # freq
    received_freq = p_profiles.get_profile_freq(new_profile_name)
    assert new_freq == int(received_freq)
    # varBinds - this verification is very case specific as profile row and expanded row does not have same Web element container
    p_profiles.expand_profile(new_profile_name)
    varBind = p_profiles.get_profile_varbind(new_profile_name)
    assert new_varBind == varBind
    p_profiles.delete_profile_from_list(new_profile_name)
    exist = p_profiles.check_if_profile_is_configured(new_profile_name)
    assert exist is False
