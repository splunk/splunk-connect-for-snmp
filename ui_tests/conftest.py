import os
from datetime import datetime

import pytest
import splunklib.client as client
import splunklib.results as results
from logger.logger import Logger
from webdriver.webriver_factory import WebDriverFactory

from splunk_search import check_events_from_splunk

logger = Logger().get_logger()

def get_splunk_internal_logs(setup, minutes=5):
    """
    Fetch Splunk internal ERROR/WARN logs safely.
    Never crashes test execution.
    """

    REQUIRED_KEYS = ("splunkd_url", "splunk_user", "splunk_password")

    # 🛑 If setup is missing or incomplete, skip cleanly
    if not setup or not all(k in setup for k in REQUIRED_KEYS):
        return [{
            "warning": "Splunk setup not available for this test"
        }]

    query = (
        'search index=_internal '
        '(log_level=ERROR OR log_level=WARN)'
    )

    try:
        return check_events_from_splunk(
            start_time=f"-{minutes}m@m",
            url=setup["splunkd_url"],
            user=setup["splunk_user"],
            password=setup["splunk_password"],
            query=query,
        )
    except Exception as e:
        return [{
            "error": f"Splunk query failed: {str(e)}"
        }]



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
            print("\n--- Splunk _internal ERROR/WARN logs (last 10 min) ---")

            logs = get_splunk_internal_logs(
                item.funcargs.get("setup"),
                minutes=10,
            )

            if not logs:
                print("ℹ️ No Splunk ERROR/WARN logs found")
            else:
                for log in logs:
                    if "error" in log:
                        print(f"❌ Error fetching logs: {log['error']}")
                    elif "warning" in log:
                        print(f"⚠️ {log['warning']}")
                    else:
                        timestamp = log.get("_time", "N/A")
                        source = log.get("source", "N/A")
                        message = log.get("_raw", "N/A")
                        print(f"{timestamp} | {source} | {message}")

        except Exception as e:
            print("❌ Splunk internal log capture failed:", e)
