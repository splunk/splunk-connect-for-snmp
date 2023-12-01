from logger.logger import Logger
from selenium.webdriver.common.keys import Keys

logger = Logger().get_logger()


def clear_input(input_element):
    logger.info("Clearing input")
    text = input_element.get_attribute("value")
    for num in range(len(text)):
        input_element.send_keys(Keys.BACKSPACE)
