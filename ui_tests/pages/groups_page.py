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
        logger.info("Click add new group button")
        add_group_button_xpath = "//button[@data-test='sc4snmp:new-item-button']//span"
        helper.safe_click(driver, add_group_button_xpath)
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
        logger.info("Click submit button")
        add_group_button_xpath = (
            "//button[@data-test='sc4snmp:form:submit-form-button']"
        )
        helper.safe_click(driver, add_group_button_xpath)
        # wait for group to be shown on the list
        time.sleep(5)

    def click_submit_button_for_add_device(self):
        self.click_submit_button_for_add_group()

    def click_cancel_button_for_add_device(self):
        logger.info("Click cancel button")
        cancel_button_xpath = "//button[@data-test='sc4snmp:form:cancel-button']"
        helper.safe_click(driver, cancel_button_xpath)
        helper.wait_for_modal_overlay_to_close(driver)

    def check_if_groups_is_on_list(self, group_name):
        logger.info("Checking if group is configured (is on list)")
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
        helper.safe_click(driver, delete_btn_for_group_with_name_xpath)
        time.sleep(1)

    def close_delete_popup(self):
        logger.info("Closing profile delete popup")
        close_profile_delete_popup_btn_xpath = (
            "//button[@data-test='sc4snmp:errors-modal:cancel-button']"
        )
        helper.safe_click(driver, close_profile_delete_popup_btn_xpath)
        helper.wait_for_modal_overlay_to_close(driver)

    def click_add_device_to_group(self, group_name):
        logger.info(f"Click add device to group: {group_name}")
        add_device_for_group_with_name_xpath = f"//div[@data-test='sc4snmp:group' and child::*[text()='{group_name}']]//button[@data-test='sc4snmp:group:new-device-button']"
        helper.safe_click(driver, add_device_for_group_with_name_xpath)
        time.sleep(1)

    def get_error_message_while_adding_device_with_no_data(self):
        logger.info("getting error message while adding device with no data")
        error_msg_xpath = "//p[@data-test='sc4snmp:ip-error']"
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
        logger.info("Checking if device is configured (is on group list)")
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
        helper.safe_click(driver, edit_group_button_xpath)
        add_grp_input = self._get_group_name_input()
        helper.clear_input(add_grp_input)
        add_grp_input.send_keys(new_group_name)
        self.click_submit_button_for_add_group()

    def get_submit_edited_group_name_popup_message(self):
        logger.info("Get submit edited group name popup text")
        edited_group_popup_text_xpath = "//div[@data-test='modal']//div//p"
        edited_group_popup_text = driver.find_element(
            By.XPATH, edited_group_popup_text_xpath
        )
        return edited_group_popup_text.text

    def close_edited_profile_popup(self):
        logger.info("Closing edited group popup")
        close_popup_btn_xpath = (
            "//button[@data-test='sc4snmp:errors-modal:cancel-button']"
        )
        helper.safe_click(driver, close_popup_btn_xpath)
        helper.wait_for_modal_overlay_to_close(driver)

    def delete_device_from_group(self, device_ip):
        logger.info("Delete device from group popup")
        delete_device_btn_xpath = f"//button[@data-test='sc4snmp:group-row-delete' and ancestor::tr//td[text()='{device_ip}']]"
        helper.safe_click(driver, delete_device_btn_xpath)
        time.sleep(2)
        self.confirm_delete()
        self.close_delete_popup()

    def click_edit_device(self, device_ip):
        logger.info("Click edit device button")
        edit_device_btn_xpath = f"//button[@data-test='sc4snmp:group-row-edit' and ancestor::tr//td[text()='{device_ip}']]"
        helper.safe_click(driver, edit_device_btn_xpath)
        time.sleep(2)

    def confirm_delete(self):
        logger.info("Confirm delete device from group popup")
        confirm_delete_xpath = (
            "//button[@data-test='sc4snmp:delete-modal:delete-button']"
        )
        helper.safe_click(driver, confirm_delete_xpath)

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
            "getting error message while removing group which is configured in inventory"
        )
        warning_msg_xpath = (
            "//div[@data-test-type='warning' and @data-test='message']//div"
        )
        warning_msg = driver.find_element(By.XPATH, warning_msg_xpath)
        return warning_msg.text

    def clear_groups(self):
        logger.info("remove all groups")
        group_delete_btn_xpath = (
            "//button[@data-test='sc4snmp:group:delete-group-button']"
        )
        delete_btns = driver.find_elements(By.XPATH, group_delete_btn_xpath)
        logger.info(f"Need to remove {len(delete_btns)} items")
        while len(delete_btns) > 0:
            delete_btns[0].click()
            time.sleep(1)
            self.confirm_delete()
            self.close_delete_popup()
            delete_btns = driver.find_elements(By.XPATH, group_delete_btn_xpath)
            logger.info(f" {len(delete_btns)} more items for removal")

    def click_bulk_add_to_group(self, group_name):
        logger.info(f"Click bulk-add devices to group: {group_name}")
        bulk_add_btn_xpath = f"//div[@data-test='sc4snmp:group' and child::*[text()='{group_name}']]//button[@data-test='sc4snmp:group:bulk-add-button']"
        bulk_add_btn = driver.find_element(By.XPATH, bulk_add_btn_xpath)
        bulk_add_btn.click()
        time.sleep(1)

    def switch_bulk_mode(self, mode):
        logger.info(f"Switch bulk-add mode: {mode}")
        mode_button_xpath = {
            "manual": "//button[@data-test='sc4snmp:bulk:mode-manual']",
            "paste": "//button[@data-test='sc4snmp:bulk:mode-paste']",
        }
        mode_btn = driver.find_element(By.XPATH, mode_button_xpath[mode])
        mode_btn.click()
        time.sleep(1)

    def click_bulk_add_row(self):
        logger.info("Click add row button in bulk-add grid")
        add_row_btn_xpath = (
            "//*[@data-test='sc4snmp:bulk:add-row']//button[@data-test='add-row']"
        )
        add_row_btn = driver.find_element(By.XPATH, add_row_btn_xpath)
        add_row_btn.click()
        time.sleep(1)

    def set_bulk_row_field(self, field_name, index, value):
        logger.info(f"set bulk row {index} field {field_name}: {value}")
        field_input_xpath = (
            f"//div[@data-test='sc4snmp:bulk:{field_name}-input']//span//input"
        )
        field_inputs = driver.find_elements(By.XPATH, field_input_xpath)
        field_inputs[index].send_keys(value)

    def set_bulk_row_address(self, index, address):
        self.set_bulk_row_field("address", index, address)

    def set_bulk_row_port(self, index, port):
        self.set_bulk_row_field("port", index, port)

    def set_bulk_row_community(self, index, community_string):
        self.set_bulk_row_field("community", index, community_string)

    def set_bulk_row_secret(self, index, secret):
        self.set_bulk_row_field("secret", index, secret)

    def set_bulk_row_security_engine(self, index, security_engine):
        self.set_bulk_row_field("security-engine", index, security_engine)

    def set_bulk_paste_text(self, text):
        logger.info(f"set bulk paste text: {text}")
        paste_input_xpath = "//div[@data-test='sc4snmp:bulk:paste-input']//textarea[@data-test='textbox']"
        paste_input = driver.find_element(By.XPATH, paste_input_xpath)
        paste_input.send_keys(text)

    def set_bulk_shared_field(self, field_name, value):
        logger.info(f"set bulk shared field {field_name}: {value}")
        field_input_xpath = (
            f"//div[@data-test='sc4snmp:bulk:shared-{field_name}-input']//span//input"
        )
        field_input = driver.find_element(By.XPATH, field_input_xpath)
        field_input.send_keys(value)

    def set_bulk_shared_port(self, port):
        self.set_bulk_shared_field("port", port)

    def set_bulk_shared_community(self, community_string):
        self.set_bulk_shared_field("community", community_string)

    def set_bulk_shared_secret(self, secret):
        self.set_bulk_shared_field("secret", secret)

    def set_bulk_shared_security_engine(self, security_engine):
        self.set_bulk_shared_field("security-engine", security_engine)

    def set_bulk_shared_version(self, snmp_version):
        logger.info(f"set bulk shared snmp version: {snmp_version}")
        options = {
            "From inventory": "//button[@data-test='sc4snmp:bulk:shared-version-from-inventory']",
            "1": "//button[@data-test='sc4snmp:bulk:shared-version-1']",
            "2c": "//button[@data-test='sc4snmp:bulk:shared-version-2c']",
            "3": "//button[@data-test='sc4snmp:bulk:shared-version-3']",
        }
        expander_xpath = "//button[@data-test='sc4snmp:bulk:shared-select-version']"
        expander = driver.find_element(By.XPATH, expander_xpath)
        expander.click()
        time.sleep(1)
        option = driver.find_element(By.XPATH, options[snmp_version])
        option.click()

    def click_bulk_expand_addresses(self):
        logger.info("Click expand addresses button in bulk-add")
        expand_btn_xpath = "//button[@data-test='sc4snmp:bulk:expand-button']"
        expand_btn = driver.find_element(By.XPATH, expand_btn_xpath)
        expand_btn.click()
        time.sleep(1)

    def click_bulk_submit(self):
        logger.info("Click submit button in bulk-add modal")
        submit_btn_xpath = "//button[@data-test='sc4snmp:bulk:submit-button']"
        helper.safe_click(driver, submit_btn_xpath)
        time.sleep(5)

    def click_bulk_cancel(self):
        logger.info("Click cancel button in bulk-add modal")
        cancel_btn_xpath = "//button[@data-test='sc4snmp:bulk:cancel-button']"
        helper.safe_click(driver, cancel_btn_xpath)
        helper.wait_for_modal_overlay_to_close(driver)

    def get_number_of_bulk_rows(self):
        logger.info("getting number of rows in bulk-add grid")
        row_xpath = "//*[@data-test='sc4snmp:bulk:row']"
        rows = driver.find_elements(By.XPATH, row_xpath)
        return len(rows)

    def get_bulk_row_error_messages(self):
        logger.info("getting bulk-add row error messages")
        error_xpath = "//p[@data-test='sc4snmp:bulk:row-error']"
        errors = driver.find_elements(By.XPATH, error_xpath)
        return [el.text for el in errors]

    def is_bulk_empty_grid_hint_present(self):
        logger.info("checking if bulk-add empty grid hint is present")
        hint_xpath = "//*[@data-test='sc4snmp:bulk:empty-grid-hint']"
        return len(driver.find_elements(By.XPATH, hint_xpath)) > 0

    def is_bulk_submit_enabled(self):
        logger.info("checking if bulk-add submit button is enabled")
        submit_btn_xpath = "//button[@data-test='sc4snmp:bulk:submit-button']"
        submit_btn = driver.find_element(By.XPATH, submit_btn_xpath)
        return submit_btn.is_enabled()