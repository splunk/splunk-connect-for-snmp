import os
from datetime import datetime

import pytest
import splunklib.client as client
import splunklib.results as results
from logger.logger import Logger
from splunk_search import check_events_from_splunk
from webdriver.webriver_factory import WebDriverFactory

logger = Logger().get_logger()


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


# -----------------------------------------------------------
# Fetch latest workflow logs (not only ERROR/WARN)
# -----------------------------------------------------------
def get_recent_splunk_logs(url, user, password, minutes=10, limit=50):
    """
    Fetch latest N logs from important SC4SNMP components
    to understand application workflow.
    """
    logger.info(f"Fetching Splunk logs: last {minutes} minutes, limit {limit}")

    # query = f"""
    #     search earliest=-{minutes}m@m
    #     (
    #         index=_internal
    #         OR index=netops
    #         OR index=em_logs
    #     )
    #     | sort - _time
    #     | head {limit}
    # """

    query = f"""
        | multisearch 
            [ search earliest=-{minutes}m@m (index=_internal OR index=netops OR index=em_logs) ]
            [ mpreview index=netmetrics ]
        | sort - _time
        | head {limit}
    """

    try:
        logger.debug(f"Executing Splunk query: {query[:100]}...")
        logs = check_events_from_splunk(
            start_time=f"-{minutes}m@m",
            url=url,
            user=user,
            password=password,
            query=query,
        )
        logger.info(
            f"Successfully retrieved {len(logs) if logs else 0} logs from Splunk"
        )
        return logs
    except Exception as e:
        logger.error(f"Splunk query failed: {e}", exc_info=True)
        return []


# def format_log_output(log):
#     """Format log for readable output (similar to kubectl logs style)"""
#     timestamp = log.get("_time", "N/A")
#     index = log.get("index", "unknown")
#     source = log.get("source", "unknown")
#     raw = log.get("_raw", str(log))

#     # Truncate very long logs
#     if len(raw) > 200:
#         raw = raw[:200] + "..."

#     return f"[{index}] {timestamp} | {source} | {raw}"


def dump_splunk_workflow_logs(url, user, password, minutes=10, limit=50):
    """
    Dump Splunk workflow logs using logger (similar to dump_kubernetes_logs).
    """
    logger.info("=" * 60)
    logger.info("SPLUNK WORKFLOW LOGS (Last 10 minutes, Latest 50 events)")
    logger.info("=" * 60)

    try:
        logs = get_recent_splunk_logs(
            url=url,
            user=user,
            password=password,
            minutes=minutes,
            limit=limit,
        )

        if not logs:
            logger.warning("No recent Splunk logs found")
        else:
            logger.info(f"Found {len(logs)} events:")
            logger.info("")  # Empty line for readability
            logger.info(f"Found  events:{logs}")

            for i, log in enumerate(logs, 1):
                logger.info(f"EVENT {i}: {log}")

        logger.info("")  # Empty line
        logger.info("=" * 60)
        logger.info("END OF WORKFLOW LOGS")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Error during Splunk workflow log dump: {e}", exc_info=True)


# -----------------------------------------------------------
# Auto dump logs when test fails
# -----------------------------------------------------------
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Auto dump workflow logs when UI test fails"""
    outcome = yield
    report = outcome.get_result()

    if report.when != "call":
        return

    if report.failed:
        logger.warning("!" * 60)
        logger.warning("UI TEST FAILED - DUMPING WORKFLOW LOGS")
        logger.warning(f"Test: {item.nodeid}")
        logger.warning("!" * 60)

        try:
            config = item.config

            host = config.getoption("--splunk-host", default=None)
            user = config.getoption("--splunk-user", default=None)
            password = config.getoption("--splunk-password", default=None)

            if not host or not user or not password:
                logger.warning(
                    "Splunk configuration not provided. "
                    "Use --splunk-host, --splunk-user, --splunk-password"
                )
                return

            url = f"https://{host}:8089"
            logger.info(f"Connecting to Splunk at {url}")

            # Dump workflow logs
            dump_splunk_workflow_logs(
                url=url,
                user=user,
                password=password,
                minutes=10,
                limit=50,
            )

        except Exception as e:
            logger.error(f"Splunk log capture failed: {e}", exc_info=True)
