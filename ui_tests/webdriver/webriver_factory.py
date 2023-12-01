import time

import config.config as config
import pytest
from logger.logger import Logger
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

logger = Logger().get_logger()


class WebDriverFactory:
    _driver = None

    @classmethod
    def get_driver(cls):
        if cls._driver is None:
            logger.info(f"Execution type: {config.EXECUTION_TYPE}")
            logger.info(f"UI URL: {config.UI_URL}")
            chrome_options = Options()
            if config.EXECUTION_TYPE != "local":
                logger.info(f"Enable headless execution")
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--disable-gpu")
                chrome_options.add_argument("--window-size=1920x1080")
            # web_driver = webdriver.Chrome(options=chrome_options)

            cls._driver = webdriver.Chrome(
                service=ChromeService(ChromeDriverManager().install()),
                options=chrome_options,
            )

            cls._driver.maximize_window()
            cls._driver.implicitly_wait(config.IMPLICIT_WAIT_TIMER)
            cls._driver.get(config.UI_URL)
        return cls._driver

    @classmethod
    def close_driver(cls):
        if cls._driver is not None:
            logger.info("Killing webdriver and closing browser")
            cls._driver.quit()
            cls._driver = None
        else:
            logger.warn("Unable to kill driver it does not exist")

    @classmethod
    def restart_driver(cls):
        cls.close_driver()
        return cls.get_driver()
