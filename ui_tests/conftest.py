import os
from datetime import datetime

import pytest
from logger.logger import Logger
import splunklib.client as client
import splunklib.results as results
from webdriver.webriver_factory import WebDriverFactory

logger = Logger().get_logger()


def read_splunk_log_file(lines=50):
    """
    Read last N lines from Splunk splunkd.log
    Works for Docker-based Splunk with volume mount:
    $PWD/splunk-data:/opt/splunk/var
    """
    log_file = os.path.join(
        os.getcwd(),
        "splunk-data",
        "log",
        "splunk",
        "splunkd.log",
    )

    try:
        if os.path.exists(log_file):
            with open(log_file, "r") as f:
                return f.readlines()[-lines:]
        else:
            return [f"splunkd.log not found at {log_file}"]
    except Exception as e:
        return [f"Failed to read splunkd.log: {e}"]


def pytest_addoption(parser):
    parser.addoption(
        "--device-simulator",
        action="store",
        dest="device-simulator",
        default="127.0.0.1",
        help="Device Simulator external IP, basically external IP of VM",
    )


@pytest.fixture(scope="function")
def setup(request):
    config = {}
    host = request.config.getoption("--splunk-host")
    config["splunkd_url"] = "https://" + host + ":8089"
    config["splunk_user"] = request.config.getoption("--splunk-user")
    config["splunk_password"] = request.config.getoption("--splunk-password")
    config["device_simulator"] = request.config.getoption("device-simulator")

    return config


def pytest_unconfigure():
    logger.info("Closing Web Driver")
    WebDriverFactory.close_driver()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    outcome = yield

    if outcome.excinfo is not None:
        print("\n========== UI TEST FAILURE DEBUG ==========")
        print(f"Test failed: {item.nodeid}")

        # Print Python exception
        exc_type, exc_value, _ = outcome.excinfo
        print(f"Exception type: {exc_type.__name__}")
        print(f"Exception message: {exc_value}")

        # Try to collect browser info (if Selenium is running)
        try:
            from webdriver.webriver_factory import WebDriverFactory

            driver = WebDriverFactory.get_driver()

            print("Current URL:", driver.current_url)
            print("Page title:", driver.title)

            if "login" in driver.title.lower():
                print("Reason: Redirected to login page (session/auth issue)")

        except Exception as e:
            print("Browser info not available:", e)


        try:
            print("\n--- Splunk splunkd.log (last 50 lines) ---")
            for line in read_splunk_log_file(50):
                print(line.rstrip())
        except Exception as e:
            print("Splunk log capture failed:", e)


        print("==========================================\n")
