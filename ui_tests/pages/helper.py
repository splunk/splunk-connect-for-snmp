from logger.logger import Logger
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = Logger().get_logger()

MODAL_OVERLAY_XPATH = "//div[@data-test='modal-overlay']"


def clear_input(input_element):
    logger.info("Clearing input")
    input_element.send_keys(Keys.CONTROL, "a")
    input_element.send_keys(Keys.BACKSPACE)


def wait_for_modal_overlay_to_close(driver, timeout=10):
    logger.info("Waiting for modal overlay to close")
    WebDriverWait(driver, timeout).until(
        EC.invisibility_of_element_located((By.XPATH, MODAL_OVERLAY_XPATH))
    )


def safe_click(driver, xpath, timeout=30):
    """Reacquire the element while React renders or a modal finishes closing."""

    def click_when_ready(current_driver):
        try:
            element = EC.element_to_be_clickable((By.XPATH, xpath))(current_driver)
            if not element:
                return False
            element.click()
            return element
        except (ElementClickInterceptedException, StaleElementReferenceException):
            return False

    return WebDriverWait(driver, timeout).until(
        click_when_ready, message=f"Unable to click {xpath}"
    )


def wait_for_visible(driver, xpath, timeout=30):
    return WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located((By.XPATH, xpath))
    )


def get_visible_text(driver, xpath, timeout=30):
    def text_when_ready(current_driver):
        element = EC.visibility_of_element_located((By.XPATH, xpath))(current_driver)
        return element.text if element else False

    return WebDriverWait(
        driver, timeout, ignored_exceptions=(StaleElementReferenceException,)
    ).until(text_when_ready)


def submit_form(driver, xpath, timeout=30):
    button = safe_click(driver, xpath, timeout)

    def completed(current_driver):
        try:
            if not button.is_displayed():
                return True
        except StaleElementReferenceException:
            return True
        feedback = current_driver.find_elements(
            By.XPATH,
            "//div[@data-test='modal']//div[@data-test='content']"
            " | //p[contains(@data-test, 'error')]",
        )
        return any(element.is_displayed() and element.text for element in feedback)

    WebDriverWait(
        driver, timeout, ignored_exceptions=(StaleElementReferenceException,)
    ).until(completed)


def entry_is_listed(driver, xpath, text, expected=None, timeout=30):
    def present(current_driver):
        return any(
            element.text == text
            for element in current_driver.find_elements(By.XPATH, xpath)
        )

    if expected is None:
        return present(driver)
    WebDriverWait(
        driver, timeout, ignored_exceptions=(StaleElementReferenceException,)
    ).until(
        lambda current_driver: present(current_driver) == expected,
        message=f"Expected {text!r} in {xpath}: {expected}",
    )
    return expected
