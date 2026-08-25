from logger.logger import Logger
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = Logger().get_logger()

MODAL_OVERLAY_XPATH = "//div[@data-test='modal-overlay']"


def clear_input(input_element):
    logger.info("Clearing input")
    text = input_element.get_attribute("value")
    for _ in range(len(text)):
        input_element.send_keys(Keys.BACKSPACE)


def wait_for_modal_overlay_to_close(driver, timeout=10):
    logger.info("Waiting for modal overlay to close")
    WebDriverWait(driver, timeout).until(
        EC.invisibility_of_element_located((By.XPATH, MODAL_OVERLAY_XPATH))
    )


def safe_click(driver, xpath, timeout=10, retries=3):
    """Click the element at xpath, retrying if a still-closing modal overlay
    from a previous action intercepts the click."""
    last_error = None
    for attempt in range(retries):
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            element.click()
            return element
        except ElementClickInterceptedException as e:
            last_error = e
            logger.info(
                f"Click intercepted (attempt {attempt + 1}/{retries}), waiting for modal overlay to close"
            )
            try:
                wait_for_modal_overlay_to_close(driver, timeout)
            except TimeoutException:
                logger.info(
                    "Modal overlay did not close within timeout, retrying click anyway"
                )
    raise last_error
