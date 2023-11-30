import re
import time

from logger.logger import Logger
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver.webriver_factory import WebDriverFactory

logger = Logger().get_logger()
driver = WebDriverFactory.get_driver()


class HeaderPage:
    def switch_to_profiles(self):
        self._switch_to_page("profiles")

    def switch_to_groups(self):
        self._switch_to_page("groups")

    def switch_to_inventory(self):
        self._switch_to_page("inventory")

    def _switch_to_page(self, page_name):
        logger.info(f"Switching to {page_name} tab")
        page_button_xpath = {
            "profiles": "//button[@data-test='sc4snmp:profiles-tab']",
            "groups": "//button[@data-test='sc4snmp:groups-tab']",
            "inventory": "//button[@data-test='sc4snmp:inventory-tab']",
        }
        xpath_button = page_button_xpath[page_name]
        tab = driver.find_element(By.XPATH, xpath_button)
        tab.click()
        page_table_xpath = {
            "profiles": "//div[@data-test='sc4snmp:profiles-table']",
            "groups": "//div[@data-test='sc4snmp:group-table']",
            "inventory": "//div[@data-test='sc4snmp:inventory-table']",
        }
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, page_table_xpath[page_name]))
        )

    def apply_changes(self):
        logger.info("Apply changes")
        apply_changes_button_xpath = (
            "//button[@data-test='sc4snmp:apply-changes-button']"
        )
        apply_btn = driver.find_element(By.XPATH, apply_changes_button_xpath)
        apply_btn.click()
        time.sleep(3)

    def close_configuration_applied_notification_popup(self):
        logger.info("Close configuration applied popup")
        popup_xpath = "//button[@data-test='sc4snmp:errors-modal:cancel-button']"
        close_popup_button = driver.find_element(By.XPATH, popup_xpath)
        close_popup_button.click()
        time.sleep(3)

    def get_time_to_upgrade(self):
        logger.info("Get time to upgrade")
        popup_text_xpath = "//div[@data-test='modal']//div//p"
        popup_txt_element = driver.find_element(By.XPATH, popup_text_xpath)
        text = popup_txt_element.text
        matches = re.search(r"\d+", text)
        number = int(matches.group())
        logger.info(f"Extracted number: {number}")
        time.sleep(3)
        return number

    def get_popup_error_message(self):
        logger.info("Get popup error message")
        popup_text_xpath = "//div[@data-test='modal']//div//div"
        popup_txt_element = driver.find_element(By.XPATH, popup_text_xpath)
        return popup_txt_element.text

    def close_error_popup(self):  # two similar methods on profile page
        logger.info("Close popup error message")
        close_profile_delete_popup_btn_xpath = (
            "//button[@data-test='sc4snmp:errors-modal:cancel-button']"
        )
        close_btn = driver.find_element(By.XPATH, close_profile_delete_popup_btn_xpath)
        close_btn.click()
        time.sleep(1)
