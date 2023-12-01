import time

import pages.helper as helper
from logger.logger import Logger
from selenium.webdriver.common.by import By
from webdriver.webriver_factory import WebDriverFactory

logger = Logger().get_logger()
driver = WebDriverFactory.get_driver()


class GroupsPage:
    def check_if_groups_table_is_displayed(self):
        logger.info("Check if groups page is displayed")
        groups_table_xpath = "//div[@data-test='sc4snmp:group-table']"
        groups_container = driver.find_element(By.XPATH, groups_table_xpath)
        return groups_container.is_displayed()

    def click_add_new_group_button(self):
        logger.info(f"Click add new group button")
        add_group_button_xpath = "//button[@data-test='sc4snmp:new-item-button']//span"
        add_grp_btn = driver.find_element(By.XPATH, add_group_button_xpath)
        add_grp_btn.click()
        time.sleep(1)

    def set_group_name(self, group_name):
        logger.info(f"Set group name: {group_name}")
        add_grp_input = self._get_group_name_input()
        add_grp_input.send_keys(group_name)

    def _get_group_name_input(self):
        add_group_input_xpath = (
            "//div[@data-test='sc4snmp:form:group-name-input']//span//input"
        )
        add_grp_input = driver.find_element(By.XPATH, add_group_input_xpath)
        return add_grp_input

    def click_submit_button_for_add_group(self):
        logger.info(f"Click submit button")
        add_group_button_xpath = (
            "//button[@data-test='sc4snmp:form:submit-form-button']"
        )
        add_grp_btn = driver.find_element(By.XPATH, add_group_button_xpath)
        add_grp_btn.click()
        # wait for group to be shown on the list
        time.sleep(5)

    def click_submit_button_for_add_device(self):
        self.click_submit_button_for_add_group()

    def click_cancel_button_for_add_device(self):
        logger.info(f"Click cancel button")
        cancel_button_xpath = "//button[@data-test='sc4snmp:form:cancel-button']"
        cancel_btn = driver.find_element(By.XPATH, cancel_button_xpath)
        cancel_btn.click()

    def check_if_groups_is_on_list(self, group_name):
        logger.info(f"Checking if group is configured (is on list)")
        group_entry_on_list_xpath = "//div[@data-test='sc4snmp:group']//p"
        groups_entries = driver.find_elements(By.XPATH, group_entry_on_list_xpath)
        for el in groups_entries:
            # logger.info(f"group name >  |{el.text}|")  # debug
            if group_name == el.text:
                return True
        logger.info("Group has not been found on list")
        return False

    def delete_group_from_list(self, group_name):
        logger.info(f"Removing group from groups list: {group_name}")
        self.click_delete_group_button(group_name)
        self.confirm_delete()
        self.close_delete_popup()

    def click_delete_group_button(self, group_name):
        logger.info(f"Clicking delete group button for: {group_name}")
        delete_btn_for_group_with_name_xpath = f"//div[@data-test='sc4snmp:group' and child::*[text()='{group_name}']]//button[@data-test='sc4snmp:group:delete-group-button']"
        delete_btn = driver.find_element(By.XPATH, delete_btn_for_group_with_name_xpath)
        delete_btn.click()
        time.sleep(1)

    def close_delete_popup(self):
        logger.info(f"Closing profile delete popup")
        close_profile_delete_popup_btn_xpath = (
            "//button[@data-test='sc4snmp:errors-modal:cancel-button']"
        )
        close_btn = driver.find_element(By.XPATH, close_profile_delete_popup_btn_xpath)
        close_btn.click()
        time.sleep(1)

    def click_add_device_to_group(self, group_name):
        logger.info(f"Click add device to group: {group_name}")
        add_device_for_group_with_name_xpath = f"//div[@data-test='sc4snmp:group' and child::*[text()='{group_name}']]//button[@data-test='sc4snmp:group:new-device-button']"
        add_device_btn = driver.find_element(
            By.XPATH, add_device_for_group_with_name_xpath
        )
        add_device_btn.click()
        time.sleep(1)

    def get_error_message_while_adding_device_with_no_data(self):
        logger.info(f"getting error message while adding device with no data")
        error_msg_xpath = f"//p[@data-test='sc4snmp:ip-error']"
        err_msg = driver.find_element(By.XPATH, error_msg_xpath)
        return err_msg.text

    def get_number_of_devices_for_group(self, group_name):
        logger.info(f"getting number of devices for group: {group_name}")
        device_row_xpath = "//tr[@data-test='sc4snmp:group-row']"
        rows = driver.find_elements(By.XPATH, device_row_xpath)
        return len(rows)

    def set_device_ip(self, device_ip, edit=False):
        logger.info(f"set device ip: {device_ip}")
        device_ip_field_xpath = "//div[@data-test='sc4snmp:form:ip-input']//span//input"
        ip_field = driver.find_element(By.XPATH, device_ip_field_xpath)
        if edit:
            helper.clear_input(ip_field)
        ip_field.send_keys(device_ip)

    def check_if_device_is_configured(self, device_ip):
        logger.info(f"Checking if device is configured (is on group list)")
        device_entry_on_list_xpath = "//td[@data-test='sc4snmp:host-address']"
        devices_entries = driver.find_elements(By.XPATH, device_entry_on_list_xpath)
        for el in devices_entries:
            # logger.info(f"device name >  |{el.text}|")  # debug
            if device_ip == el.text:
                return True
        logger.info("Device has not been found on list")
        return False

    def edit_group_name(self, group_name, new_group_name):
        logger.info(f"change group name: {group_name} -> {new_group_name}")
        edit_group_button_xpath = f"//div[@data-test='sc4snmp:group' and child::*[text()='{group_name}']]//button[@data-test='sc4snmp:group:edit-group-button']"
        edit_group_btn = driver.find_element(By.XPATH, edit_group_button_xpath)
        edit_group_btn.click()
        add_grp_input = self._get_group_name_input()
        helper.clear_input(add_grp_input)
        add_grp_input.send_keys(new_group_name)
        self.click_submit_button_for_add_group()

    def get_submit_edited_group_name_popup_message(self):
        logger.info(f"Get submit edited group name popup text")
        edited_group_popup_text_xpath = f"//div[@data-test='modal']//div//p"
        edited_group_popup_text = driver.find_element(
            By.XPATH, edited_group_popup_text_xpath
        )
        return edited_group_popup_text.text

    def close_edited_profile_popup(self):
        logger.info(f"Closing edited group popup")
        close_popup_btn_xpath = (
            f"//button[@data-test='sc4snmp:errors-modal:cancel-button']"
        )
        close_popup_btn = driver.find_element(By.XPATH, close_popup_btn_xpath)
        close_popup_btn.click()
        time.sleep(2)

    def delete_device_from_group(self, device_ip):
        logger.info(f"Delete device from group popup")
        delete_device_btn_xpath = f"//button[@data-test='sc4snmp:group-row-delete' and ancestor::tr//td[text()='{device_ip}']]"
        delete_device_btn = driver.find_element(By.XPATH, delete_device_btn_xpath)
        delete_device_btn.click()
        time.sleep(2)
        self.confirm_delete()
        self.close_delete_popup()

    def click_edit_device(self, device_ip):
        logger.info(f"Click edit device button")
        edit_device_btn_xpath = f"//button[@data-test='sc4snmp:group-row-edit' and ancestor::tr//td[text()='{device_ip}']]"
        edit_device_btn = driver.find_element(By.XPATH, edit_device_btn_xpath)
        edit_device_btn.click()
        time.sleep(2)

    def confirm_delete(self):
        logger.info(f"Confirm delete device from group popup")
        confirm_delete_xpath = (
            "//button[@data-test='sc4snmp:delete-modal:delete-button']"
        )
        confirm_btn = driver.find_element(By.XPATH, confirm_delete_xpath)
        confirm_btn.click()
        time.sleep(1)

    def set_device_port(self, port, edit=False):
        logger.info(f"set device port: {port}")
        self._set_group_field("port", port, edit)

    def set_community_string(self, community_string, edit=False):
        logger.info(f"set device community string: {community_string}")
        self._set_group_field("community_string", community_string, edit)

    def set_secret(self, secret, edit=False):
        logger.info(f"set device secret: {secret}")
        self._set_group_field("secret", secret, edit)

    def set_security_engine(self, security_engine, edit=False):
        logger.info(f"set security engine: {security_engine}")
        self._set_group_field("security_engine", security_engine, edit)

    def _set_group_field(self, field_name, value, edit=False):
        xpath = {
            "port": "//div[@data-test='sc4snmp:form:port-input']//span//input",
            "community_string": "//div[@data-test='sc4snmp:form:community-input']//span//input",
            "secret": "//div[@data-test='sc4snmp:form:secret-input']//span//input",
            "security_engine": "//div[@data-test='sc4snmp:form:security-engine-input']//span//input",
        }
        field_input = driver.find_element(By.XPATH, xpath[field_name])
        if edit:
            helper.clear_input(field_input)
        field_input.send_keys(value)

    def set_snmp_version(self, snmp_version):
        logger.info(f"set device snmp version: {snmp_version}")
        options = {
            "From inventory": "//button[@data-test='sc4snmp:form:version-from-inventory']",
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

    def get_device_port(self, device_ip):
        logger.info(f"get device port: {device_ip}")
        return self._get_group_field_value("port", device_ip)

    def get_device_snmp_version(self, device_ip):
        logger.info(f"get device snmp_version: {device_ip}")
        return self._get_group_field_value("snmp_version", device_ip)

    def get_device_community_string(self, device_ip):
        logger.info(f"get device community string: {device_ip}")
        return self._get_group_field_value("community_string", device_ip)

    def get_device_secret(self, device_ip):
        logger.info(f"get device secret: {device_ip}")
        return self._get_group_field_value("secret", device_ip)

    def get_device_security_engine(self, device_ip):
        logger.info(f"get device security engine {device_ip}")
        return self._get_group_field_value("security_engine", device_ip)

    def _get_group_field_value(self, field, device_ip):
        xpath = {
            "port": f"//td[@data-test='sc4snmp:host-port' and ancestor::tr//td[text()='{device_ip}']]",
            "snmp_version": f"//td[@data-test='sc4snmp:host-version' and ancestor::tr//td[text()='{device_ip}']]",
            "community_string": f"//td[@data-test='sc4snmp:host-community' and ancestor::tr//td[text()='{device_ip}']]",
            "secret": f"//td[@data-test='sc4snmp:host-secret' and ancestor::tr//td[text()='{device_ip}']]",
            "security_engine": f"//td[@data-test='sc4snmp:host-security-engine' and ancestor::tr//td[text()='{device_ip}']]",
        }
        community = driver.find_element(By.XPATH, xpath[field])
        return community.text

    def get_warning_message_when_removing_group_which_is_configured_in_inventory(self):
        logger.info(
            f"getting error message while removing group which is configured in inventory"
        )
        warning_msg_xpath = (
            f"//div[@data-test-type='warning' and @data-test='message']//div"
        )
        warning_msg = driver.find_element(By.XPATH, warning_msg_xpath)
        return warning_msg.text

    def clear_groups(self):
        logger.info(f"remove all groups")
        group_delete_btn_xpath = (
            f"//button[@data-test='sc4snmp:group:delete-group-button']"
        )
        delete_btns = driver.find_elements(By.XPATH, group_delete_btn_xpath)
        logger.info(f"Need to remove {len(delete_btns)} items")
        while len(delete_btns) > 0:
            delete_btns[0].click()
            time.sleep(1)
            self.confirm_delete()
            self.close_delete_popup()
            time.sleep(1)
            delete_btns = driver.find_elements(By.XPATH, group_delete_btn_xpath)
            logger.info(f" {len(delete_btns)} more items for removal")
