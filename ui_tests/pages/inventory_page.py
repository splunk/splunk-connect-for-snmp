import time

import pages.helper as helper
import selenium.common.exceptions
from logger.logger import Logger
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver.webriver_factory import WebDriverFactory

logger = Logger().get_logger()
driver = WebDriverFactory.get_driver()


class InventoryPage:
    def check_if_inventory_table_is_displayed(self):
        logger.info("Check if inventory page is displayed")
        inventory_table_xpath = "//div[@data-test='sc4snmp:inventory-table']"
        inventory_container = driver.find_element(By.XPATH, inventory_table_xpath)
        return inventory_container.is_displayed()

    def check_if_entry_is_on_list(self, host_ip):
        logger.info(f"Checking if host/group entry is configured (is on list)")
        entries_on_list_xpath = "//td[@data-test='sc4snmp:inventory-address']"
        entries = driver.find_elements(By.XPATH, entries_on_list_xpath)
        logger.info(f"list length: {len(entries)}")
        for el in entries:
            # logger.info(f"entry name >  |{el.text}|")  # debug
            if host_ip == el.text:
                return True
        logger.info("Entry has not been found on list")
        return False

    def click_add_new_device_group_button(self):
        logger.info(f"Click add new device/group entry button")
        add_group_device_button_xpath = (
            "//button[@data-test='sc4snmp:new-item-button']//span//span"
        )
        add_grp_device_btn = driver.find_element(
            By.XPATH, add_group_device_button_xpath
        )
        add_grp_device_btn.click()
        time.sleep(3)

    def click_submit_button_for_add_entry(self):
        self._click_submit_button()

    def _click_submit_button(self):
        logger.info(f"Click submit button")
        add_group_device_item_button_xpath = (
            "//button[@data-test='sc4snmp:form:submit-form-button']"
        )
        add_grp_device_btn = driver.find_element(
            By.XPATH, add_group_device_item_button_xpath
        )
        add_grp_device_btn.click()
        time.sleep(5)  # wait for group to be shown on the list

    def click_submit_button_for_edit_entry(self):
        self._click_submit_button()

    def delete_entry_from_list(self, host_ip):
        logger.info(f"Removing entry from inventory list: {host_ip}")
        delete_btn_for_inventory_with_host_ip_xpath = f"//button[@data-test='sc4snmp:inventory-row-delete' and ancestor::tr//td[text()='{host_ip}']]"
        delete_btn = driver.find_element(
            By.XPATH, delete_btn_for_inventory_with_host_ip_xpath
        )
        delete_btn.click()
        time.sleep(1)
        self.confirm_delete()
        self.close_delete_popup()

    def close_delete_popup(self):
        logger.info(f"Closing inventory delete popup")
        self._close_notification_popup()

    def _close_notification_popup(self):
        close_inventory_delete_popup_btn_xpath = (
            "//button[@data-test='sc4snmp:errors-modal:cancel-button']"
        )
        close_btn = driver.find_element(
            By.XPATH, close_inventory_delete_popup_btn_xpath
        )
        close_btn.click()
        time.sleep(1)

    def close_edit_inventory_entry(self):
        logger.info(f"Closing inventory edit popup")
        self._close_notification_popup()

    def confirm_delete(self):
        logger.info(f"Confirm delete entry")
        confirm_delete_xpath = (
            "//button[@data-test='sc4snmp:delete-modal:delete-button']"
        )
        confirm_btn = driver.find_element(By.XPATH, confirm_delete_xpath)
        confirm_btn.click()
        time.sleep(1)

    def set_community_string(self, community_string, edit=False):
        logger.info(f"Set community string: {community_string}")
        community_input_field_xpath = (
            "//div[@data-test='sc4snmp:form:community-input']//span//input"
        )
        community_input_field = driver.find_element(
            By.XPATH, community_input_field_xpath
        )
        if edit:
            helper.clear_input(community_input_field)
        community_input_field.send_keys(community_string)

    def click_edit_inventory_entry(self, host_ip):
        logger.info(f"Edit entry from inventory list with: {host_ip}")
        edit_inventory_entry_btn_xpath = f"//button[@data-test='sc4snmp:inventory-row-edit' and ancestor::tr//td[text()='{host_ip}']]"
        edit_inventory_entry_btn = driver.find_element(
            By.XPATH, edit_inventory_entry_btn_xpath
        )
        edit_inventory_entry_btn.click()

    def get_edit_inventory_notice(self):
        logger.info(f"Get edited inventory popup text")
        edited_inventory_popup_text_xpath = f"//div[@data-test='modal']//div//p"
        edited_inventory_popup_text = driver.find_element(
            By.XPATH, edited_inventory_popup_text_xpath
        )
        return edited_inventory_popup_text.text

    def select_group_inventory_type(self):
        logger.info(f"Select group inventory type")
        group_inventory_type_btn_xpath = (
            f"//button[@data-test='sc4snmp:form:inventory-type-group']"
        )
        group_inventory_type_btn = driver.find_element(
            By.XPATH, group_inventory_type_btn_xpath
        )
        group_inventory_type_btn.click()

    def get_host_missing_error(self):
        logger.info(f"Get host missing error")
        return self._get_error_for_missing_or_invalid_inventory_field("host_missing")

    def get_community_string_missing_error(self):
        logger.info(f"Get community string missing error")
        return self._get_error_for_missing_or_invalid_inventory_field(
            "community_string_missing"
        )

    def get_walk_invalid_value_error(self):
        logger.info(f"Get walk interval invalid value error")
        return self._get_error_for_missing_or_invalid_inventory_field(
            "walk_invalid_value"
        )

    def _get_error_for_missing_or_invalid_inventory_field(self, field):
        xpath = {
            "host_missing": f"//p[@data-test='sc4snmp:ip-group-error']",
            "community_string_missing": f"//p[@data-test='sc4snmp:community-error']",
            "walk_invalid_value": f"//p[@data-test='sc4snmp:walk-interval-error']",
        }
        try:
            error_msg = driver.find_element(By.XPATH, xpath[field])
            return error_msg.text
        except selenium.common.exceptions.NoSuchElementException:
            return None

    def edit_device_port(self, port):
        logger.info(f"set/edit inventory device port: {port}")
        device_port_field_xpath = (
            "//div[@data-test='sc4snmp:form:port-input']//span//input"
        )
        port_field = driver.find_element(By.XPATH, device_port_field_xpath)
        helper.clear_input(port_field)
        port_field.send_keys(port)

    def select_snmp_version(self, snmp_version):
        logger.info(f"set device snmp version: {snmp_version}")
        options = {
            "1": "//button[@data-test='sc4snmp:form:version-1']",
            "2c": "//button[@data-test='sc4snmp:form:version-2c']",
            "3": "//button[@data-test='sc4snmp:form:version-3']",
        }
        snmp_version_expander_xpath = (
            "//button[@data-test='sc4snmp:form:select-version']"
        )
        expander = driver.find_element(By.XPATH, snmp_version_expander_xpath)
        expander.click()
        time.sleep(1)
        option = driver.find_element(By.XPATH, options[snmp_version])
        option.click()

    def set_host_or_group_name(self, host_ip, edit=False):
        logger.info(f"Set host/group item name: {host_ip}")
        self._set_inventory_field("host_group_name", host_ip, edit)

    def set_secret(self, secret, edit=False):
        logger.info(f"set inventory device secret: {secret}")
        self._set_inventory_field("secret", secret, edit)

    def set_security_engine(self, security_engine, edit=False):
        logger.info(f"set inventory device security engine: {security_engine}")
        self._set_inventory_field("security_engine", security_engine, edit)

    def _set_inventory_field(self, field, value, edit=False):
        xpath = {
            "host_group_name": "//div[@data-test='sc4snmp:form:group-ip-input']//span//input",
            "secret": "//div[@data-test='sc4snmp:form:secret-input']//span//input",
            "security_engine": "//div[@data-test='sc4snmp:form:security-engine-input']//span//input",
        }
        field_input = driver.find_element(By.XPATH, xpath[field])
        if edit:
            helper.clear_input(field_input)
        field_input.send_keys(value)

    def set_walk_interval(self, walk_interval):
        logger.info(f"set/edit inventory device walk interval: {walk_interval}")
        sec_engine_field_xpath = (
            "//div[@data-test='sc4snmp:form:walk-interval-input']//span//input"
        )
        sec_engine = driver.find_element(By.XPATH, sec_engine_field_xpath)
        helper.clear_input(sec_engine)
        sec_engine.send_keys(walk_interval)
        time.sleep(1)

    def set_smart_profiles(self, param):
        logger.info(f"set inventory device smart profiles enabled to: {param}")
        if param == "true" or param == "false":
            smart_profile_true_xpath = (
                f"//button[@data-test='sc4snmp:form:smart-profile-{param}']"
            )
            option = driver.find_element(By.XPATH, smart_profile_true_xpath)
            option.click()
        else:
            logger.error(
                f"Wrong parameter specified. Expected: true or false, received: {param}"
            )

    def select_profiles(self, profiles, edit=False):
        logger.info(f"select profiles: {profiles}")
        profiles_input_xpath = (
            "//div[@data-test='sc4snmp:form:profiles-multiselect']//div//input"
        )
        profile_input = driver.find_element(By.XPATH, profiles_input_xpath)
        if edit:
            profile_options_xpath = "//button[@data-test='selected-option']"
            options = driver.find_elements(By.XPATH, profile_options_xpath)
            for option in options:
                option.click()
                time.sleep(0.5)
        time.sleep(1)
        for profile in profiles:
            profile_input.send_keys(profile)
            profile_input.send_keys(Keys.ENTER)
            time.sleep(2)
            # we need to hide profile list,
            # otherwise it can break test execution and popup can intercept clicking on smart profiles
            profile_input.send_keys(Keys.ESCAPE)

    def _get_inventory_data(self, host, field):
        field_xpath = {
            "snmp_version": f"//td[@data-test='sc4snmp:inventory-version' and ancestor::tr//td[text()='{host}']]",
            "port": f"//td[@data-test='sc4snmp:inventory-port' and ancestor::tr//td[text()='{host}']]",
            "community_string": f"//td[@data-test='sc4snmp:inventory-community' and ancestor::tr//td[text()='{host}']]",
            "secret": f"//td[@data-test='sc4snmp:inventory-secret' and ancestor::tr//td[text()='{host}']]",
            "security_engine": f"//td[@data-test='sc4snmp:inventory-security-engine' and ancestor::tr//td[text()='{host}']]",
            "walk_interval": f"//td[@data-test='sc4snmp:inventory-walk-interval' and ancestor::tr//td[text()='{host}']]",
            "profiles": f"//td[@data-test='sc4snmp:inventory-profiles' and ancestor::tr//td[text()='{host}']]",
            "smart_profiles": f"//td[@data-test='sc4snmp:inventory-smart-profiles' and ancestor::tr//td[text()='{host}']]",
        }
        field = driver.find_element(By.XPATH, field_xpath[field])
        return field.text

    def get_snmp_version_for_entry(self, host):
        logger.info(f"get {host} inventory -> snmp_version")
        return self._get_inventory_data(host, "snmp_version")

    def get_port_for_entry(self, host):
        logger.info(f"get {host} inventory -> port")
        return self._get_inventory_data(host, "port")

    def get_community_string_for_entry(self, host):
        logger.info(f"get {host} inventory -> community_string")
        return self._get_inventory_data(host, "community_string")

    def get_secret_for_entry(self, host):
        logger.info(f"get {host} inventory -> secret")
        return self._get_inventory_data(host, "secret")

    def get_security_engine_for_entry(self, host):
        logger.info(f"get {host} inventory -> security_engine")
        return self._get_inventory_data(host, "security_engine")

    def get_walk_interval_for_entry(self, host):
        logger.info(f"get {host} inventory -> walk_interval")
        return self._get_inventory_data(host, "walk_interval")

    def get_profiles_for_entry(self, host):
        logger.info(f"get {host} inventory -> profiles")
        return self._get_inventory_data(host, "profiles")

    def get_smart_profiles_for_entry(self, host):
        logger.info(f"get {host} inventory -> smart_profiles")
        return self._get_inventory_data(host, "smart_profiles")

    def clear_inventory(self):
        logger.info(f"remove all inventory entries")
        delete_btn_for_inventory_with_host_ip_xpath = (
            f"//button[@data-test='sc4snmp:inventory-row-delete']"
        )
        delete_btns = driver.find_elements(
            By.XPATH, delete_btn_for_inventory_with_host_ip_xpath
        )
        logger.info(f"Need to remove {len(delete_btns)} items")
        while len(delete_btns) > 0:
            delete_btns[0].click()
            time.sleep(1)
            self.confirm_delete()
            self.close_delete_popup()
            delete_btns = driver.find_elements(
                By.XPATH, delete_btn_for_inventory_with_host_ip_xpath
            )
            logger.info(f" {len(delete_btns)} more items for removal")
