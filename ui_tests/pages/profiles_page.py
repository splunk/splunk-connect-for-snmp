import time

import pages.helper as helper
from logger.logger import Logger
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver.webriver_factory import WebDriverFactory

logger = Logger().get_logger()
driver = WebDriverFactory.get_driver()


class ProfilesPage:
    def check_if_profiles_table_is_displayed(self):
        logger.info("Check if profiles page is displayed")
        profiles_table_xpath = "//div[@data-test='sc4snmp:profiles-table']"
        profiles_container = driver.find_element(By.XPATH, profiles_table_xpath)
        return profiles_container.is_displayed()

    def click_add_profile_button(self):
        logger.info("Click Add New Profile button")
        xpath = "//button[@data-test='sc4snmp:new-item-button']"
        btn = driver.find_element(By.XPATH, xpath)
        btn.click()

    def click_submit_button(self):
        logger.info("Click Submit button")
        xpath = "//button[@data-test='sc4snmp:form:submit-form-button']"
        btn = driver.find_element(By.XPATH, xpath)
        btn.click()
        time.sleep(5)  # wait for profile to be shown on the list

    def select_profile_type(self, profile_type):
        logger.info(f"Set profile type: {profile_type}")
        profiles = {
            "standard": "//button[@data-test='sc4snmp:form:condition-standard']",
            "base": "//button[@data-test='sc4snmp:form:condition-base']",
            "smart": "//button[@data-test='sc4snmp:form:condition-smart']",
            "walk": "//button[@data-test='sc4snmp:form:condition-walk']",
            "conditional": "//button[@data-test='sc4snmp:form:condition-conditional']",
        }
        profile_type_expander_xpath = (
            "//button[@data-test='sc4snmp:form:select-condition']"
        )
        expander = driver.find_element(By.XPATH, profile_type_expander_xpath)
        expander.click()
        option = driver.find_element(By.XPATH, profiles[profile_type])
        option.click()

    def set_frequency(self, freq_value):
        logger.info(f"Setting profile frequency: {freq_value}")
        xpath = "//div[@data-test='sc4snmp:form:frequency-input']//span//input"
        freq_field = driver.find_element(By.XPATH, xpath)
        helper.clear_input(freq_field)
        # freq_field.send_keys(Keys.BACKSPACE)  # clear() is not working here
        freq_field.send_keys(freq_value)

    def set_profile_name(self, name):
        logger.info(f"Setting profile frequency: {name}")
        xpath = "//div[@data-test='sc4snmp:form:profile-name-input']//span//input"
        name_input = driver.find_element(By.XPATH, xpath)
        helper.clear_input(name_input)  # this is useful when editing profile name
        name_input.send_keys(name)

    def add_varBind(self, mcomponent, mobject=None, mindex=None):
        logger.info(f"Adding varBind: {mcomponent, mobject, mindex}")
        add_varBind_button_xpath = "//div[@data-test='sc4snmp:form:add-varbinds']//span[contains(text(),'Add varBind')]"
        add_varBind_btn = driver.find_element(By.XPATH, add_varBind_button_xpath)
        add_varBind_btn.click()
        varbind_row_xpath = "//div[@data-test='sc4snmp:form:varbind-row']"
        varBinds_rows = driver.find_elements(By.XPATH, varbind_row_xpath)
        component_xpath = (
            "//div[@data-test='sc4snmp:form:varbind-mib-component-input']/span/input"
        )
        component_input = varBinds_rows[-1].find_element(By.XPATH, component_xpath)
        component_input.send_keys(mcomponent)
        if mobject is not None:
            object_xpath = (
                "//div[@data-test='sc4snmp:form:varbind-mib-object-input']/span/input"
            )
            object_input = varBinds_rows[-1].find_element(By.XPATH, object_xpath)
            object_input.send_keys(mobject)
        if mindex is not None:
            index_xpath = (
                "//div[@data-test='sc4snmp:form:varbind-mib-index-input']/span/input"
            )
            index_input = varBinds_rows[-1].find_element(By.XPATH, index_xpath)
            index_input.send_keys(mindex)

    def edit_varBind(self, new_mcomponent, new_mobject, new_mindex):
        logger.info(
            f"Editing varBind new values: {new_mcomponent}, {new_mobject}, {new_mindex}"
        )
        varbind_row_xpath = "//div[@data-test='sc4snmp:form:varbind-row']"
        varBinds_row = driver.find_element(By.XPATH, varbind_row_xpath)
        component_xpath = (
            "//div[@data-test='sc4snmp:form:varbind-mib-component-input']/span/input"
        )
        component_input = varBinds_row.find_element(By.XPATH, component_xpath)
        helper.clear_input(component_input)
        component_input.send_keys(new_mcomponent)

        object_xpath = (
            "//div[@data-test='sc4snmp:form:varbind-mib-object-input']/span/input"
        )
        object_input = varBinds_row.find_element(By.XPATH, object_xpath)
        helper.clear_input(object_input)
        object_input.send_keys(new_mobject)

        index_xpath = (
            "//div[@data-test='sc4snmp:form:varbind-mib-index-input']/span/input"
        )
        index_input = varBinds_row.find_element(By.XPATH, index_xpath)
        helper.clear_input(index_input)
        index_input.send_keys(new_mindex)

    def check_if_profile_is_configured(self, profile_name):
        logger.info(f"Checking if profile is on profiles list: {profile_name}")
        profiles_name_xpath = "//td[@data-test='sc4snmp:profile-name']"
        profile_names = driver.find_elements(By.XPATH, profiles_name_xpath)
        for element in profile_names:
            # logger.info(f"profile name >  |{element.text}|") # debug
            if profile_name == element.text:
                return True
        logger.info("Profile has not been found on list")
        return False

    def delete_profile_from_list(self, profile_name):
        logger.info(f"Removing profile from profiles list: {profile_name}")
        self.click_delete_profile_button(profile_name)
        self._confirm_delete_profile()
        self.close_profile_delete_popup()

    def click_delete_profile_button(self, profile_name):
        logger.info(f"click delete profile button -> {profile_name}")
        delete_btn_for_profile_with_name_xpath = f"//button[@data-test='sc4snmp:profile-row-delete' and ancestor::tr//td[text()='{profile_name}']]"
        delete_btn = driver.find_element(
            By.XPATH, delete_btn_for_profile_with_name_xpath
        )
        delete_btn.click()
        time.sleep(1)

    def _confirm_delete_profile(self):
        confirm_delete_xpath = (
            "//button[@data-test='sc4snmp:delete-modal:delete-button']"
        )
        confirm_btn = driver.find_element(By.XPATH, confirm_delete_xpath)
        confirm_btn.click()
        time.sleep(1)

    def close_profile_delete_popup(self):
        logger.info(f"Closing profile delete popup")
        close_profile_delete_popup_btn_xpath = (
            "//button[@data-test='sc4snmp:errors-modal:cancel-button']"
        )
        close_btn = driver.find_element(By.XPATH, close_profile_delete_popup_btn_xpath)
        close_btn.click()
        time.sleep(1)

    def get_profile_type_for_profile_entry(self, profile_name):
        logger.info(f"getting profile type for profile {profile_name}")
        profile_type_for_profile_with_name_xpath = f"//td[@data-test='sc4snmp:profile-type' and ancestor::tr//td[text()='{profile_name}']]"
        profile_type = driver.find_element(
            By.XPATH, profile_type_for_profile_with_name_xpath
        )
        return profile_type.text

    def set_smart_profile_field(self, field_value):
        logger.info(f"Setting smart profile field {field_value}")
        smart_profile_field_xpath = (
            "//div[@data-test='sc4snmp:form:condition-field-input']//span//input"
        )
        field = driver.find_element(By.XPATH, smart_profile_field_xpath)
        field.send_keys(field_value)

    def add_smart_profile_pattern(self, pattern):
        logger.info(f"Add smart profile pattern {pattern}")
        add_pattern_button_xpath = "//span[contains(text(),'Add pattern')]"
        add_pattern_button = driver.find_element(By.XPATH, add_pattern_button_xpath)
        add_pattern_button.click()
        time.sleep(1)
        pattern_row_xpath = (
            "//div[@data-test='sc4snmp:form:field-pattern']//span//input"
        )
        pattern_rows = driver.find_elements(By.XPATH, pattern_row_xpath)
        pattern_rows[-1].send_keys(pattern)

    def check_if_frequency_setting_field_is_visible(self):
        logger.info(f"Checking if frequency setting field is visible")
        xpath = "//div[@data-test='sc4snmp:form:frequency-input']//span//input"
        try:
            freq_field = driver.find_element(By.XPATH, xpath)
            return freq_field.is_displayed()
        except Exception as e:
            return False

    def add_condition(self, field_value, operation, value):
        logger.info(f"Adding condition: {field_value}, {operation}, {value}")
        add_condition_button_xpath = (
            "//div[@data-test='sc4snmp:form:add-conditional-profile']//button"
        )
        add_condition_btn = driver.find_element(By.XPATH, add_condition_button_xpath)
        add_condition_btn.click()
        time.sleep(1)
        # set field
        set_field_xpath = (
            "//div[@data-test='sc4snmp:form:conditional-field']//span//input"
        )
        field = driver.find_element(By.XPATH, set_field_xpath)
        field.send_keys(field_value)
        # select operation
        operation_expander_xpath = (
            "//button[@data-test='sc4snmp:form:conditional-select-operation']"
        )
        operation_expander = driver.find_element(By.XPATH, operation_expander_xpath)
        operation_expander.click()
        operation_option_xpath = (
            f"//button[@data-test='sc4snmp:form:conditional-{operation}']"
        )
        operation_option = driver.find_element(By.XPATH, operation_option_xpath)
        operation_option.click()
        # set value
        value_field_xpath = (
            "//div[@data-test='sc4snmp:form:conditional-condition']//span//input"
        )
        value_field = driver.find_element(By.XPATH, value_field_xpath)
        value_field.send_keys(value)

    def click_edit_profile(self, profile_name):
        logger.info(f"Edit profile: {profile_name}")
        edit_btn_for_profile_with_name_xpath = f"//button[@data-test='sc4snmp:profile-row-edit' and ancestor::tr//td[text()='{profile_name}']]"
        edit_btn = driver.find_element(By.XPATH, edit_btn_for_profile_with_name_xpath)
        edit_btn.click()
        time.sleep(1)

    def close_edited_profile_popup(self):
        logger.info(f"Closing edited profile popup")
        close_popup_btn_xpath = (
            f"//button[@data-test='sc4snmp:errors-modal:cancel-button']"
        )
        close_popup_btn = driver.find_element(By.XPATH, close_popup_btn_xpath)
        close_popup_btn.click()
        time.sleep(2)

    def get_submit_edited_profile_text(self):
        logger.info(f"Get submit edited profile popup text")
        edited_profile_popup_text_xpath = f"//div[@data-test='modal']//div//p"
        edited_profile_popup_text = driver.find_element(
            By.XPATH, edited_profile_popup_text_xpath
        )
        return edited_profile_popup_text.text

    def get_profile_freq(self, profile_name):
        logger.info(f"Get profile frequency {profile_name}")
        profile_freq_xpath = f"//td[@data-test='sc4snmp:profile-frequency' and ancestor::tr//td[text()='{profile_name}']]"
        profile_freq = driver.find_element(By.XPATH, profile_freq_xpath)
        return profile_freq.text

    def expand_profile(self, profile_name):
        logger.info(f"Clik profile expand button: {profile_name}")
        profile_expand_btn_xpath = f"//tr[@data-test='sc4snmp:profile-row' and child::td[text()='{profile_name}']]//td[@data-test='expand']"
        profile_expand_btn = driver.find_element(By.XPATH, profile_expand_btn_xpath)
        profile_expand_btn.click()
        time.sleep(1)

    def get_profile_varbind(self, profile_name):
        logger.info(f"Get profile varBind {profile_name}")
        profile_mcomponent_xpath = (
            f"//td[@data-test='sc4snmp:profile-mib-component-expanded']//p"
        )
        mcomponent = driver.find_element(By.XPATH, profile_mcomponent_xpath)
        profile_mobject_xpath = (
            f"//td[@data-test='sc4snmp:profile-mib-object_expanded']//p"
        )
        mobject = driver.find_element(By.XPATH, profile_mobject_xpath)
        profile_mindex_xpath = (
            f"//td[@data-test='sc4snmp:profile-mib-index-expanded']//p"
        )
        mindex = driver.find_element(By.XPATH, profile_mindex_xpath)
        varBind = {
            "mcomponent": mcomponent.text,
            "mobject": mobject.text,
            "mindex": int(mindex.text),
        }
        return varBind

    def clear_profiles(self):
        logger.info(f"remove all profiles")
        profile_delete_btn_xpath = f"//button[@data-test='sc4snmp:profile-row-delete']"
        delete_btns = driver.find_elements(By.XPATH, profile_delete_btn_xpath)
        logger.info(f"Need to remove {len(delete_btns)} items")
        while len(delete_btns) > 0:
            delete_btns[0].click()
            time.sleep(1)
            self._confirm_delete_profile()
            self.close_profile_delete_popup()
            time.sleep(1)
            delete_btns = driver.find_elements(By.XPATH, profile_delete_btn_xpath)
            logger.info(f" {len(delete_btns)} more items for removal")
