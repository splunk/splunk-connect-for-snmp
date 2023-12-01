import pytest
from logger.logger import Logger
from pages.groups_page import GroupsPage
from pages.header_page import HeaderPage
from pages.inventory_page import InventoryPage
from pages.profiles_page import ProfilesPage
from webdriver.webriver_factory import WebDriverFactory

driver = WebDriverFactory().get_driver()
logger = Logger().get_logger()
p_header = HeaderPage()
p_profiles = ProfilesPage()
p_groups = GroupsPage()
p_inventory = InventoryPage()


@pytest.mark.basic
def test_check_page_title_is_correct():
    """
    Test that SC4SNMP UI page tile is correct
    """
    page_title = driver.title

    logger.info(f"Page Title: {page_title}")
    assert "SC4SNMP Manager" == page_title


@pytest.mark.basic
def test_check_selected_tab_behaviour():
    """
    Test that selected tab stays selected upon refreshing page
    check if corresponding tables are displayed
    """
    p_header.switch_to_profiles()
    url = driver.current_url
    assert "/?tab=Profiles" in url
    assert p_profiles.check_if_profiles_table_is_displayed()
    driver.refresh()
    url = driver.current_url
    assert "/?tab=Profiles" in url

    p_header.switch_to_groups()
    url = driver.current_url
    assert "/?tab=Groups" in url
    assert p_groups.check_if_groups_table_is_displayed()
    driver.refresh()
    url = driver.current_url
    assert "/?tab=Groups" in url

    p_header.switch_to_inventory()
    url = driver.current_url
    assert "/?tab=Inventory" in url
    assert p_inventory.check_if_inventory_table_is_displayed()
    driver.refresh()
    url = driver.current_url
    assert "/?tab=Inventory" in url
