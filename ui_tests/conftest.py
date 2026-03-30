import functools
import time

import pytest
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
        help="Device Simulator external IP",
    )
    parser.addoption(
        "--splunk-host",
        action="store",
        dest="splunk-host",
        default="127.0.0.1",
        help="Splunk host to connect to",
    )
    parser.addoption(
        "--splunk-user",
        action="store",
        dest="splunk-user",
        default="admin",
        help="Splunk username for authentication",
    )
    parser.addoption(
        "--splunk-password",
        action="store",
        dest="splunk-password",
        default="changeme",
        help="Splunk password for authentication",
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
# Wait decorator (CI safe)
# -----------------------------------------------------------
def wait_for_splunk_data(timeout=60, interval=5):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):

            url = kwargs.get("url")
            user = kwargs.get("user")
            password = kwargs.get("password")
            start = time.time()

            while time.time() - start < timeout:
                logs = get_recent_splunk_logs(
                    url=url,
                    user=user,
                    password=password,
                    minutes=5,
                    limit=5,
                )

                if logs:
                    logger.info("Splunk data detected ")
                    break

                logger.info("Waiting for Splunk data...")
                time.sleep(interval)
            else:
                logger.warning("Timeout waiting for Splunk data ")

            return func(*args, **kwargs)

        return wrapper

    return decorator


# -----------------------------------------------------------
# Fetch workflow logs
# -----------------------------------------------------------
def get_recent_splunk_logs(url, user, password, minutes=10, limit=5):

    query = f"""
        | union 
            [ search earliest=-{minutes}m@m index=_internal | sort - _time | head {limit} ]
            [ search earliest=-{minutes}m@m index=netops | sort - _time | head {limit} ]
            [ search earliest=-{minutes}m@m index=em_logs | sort - _time | head {limit} ]
            [ | mpreview index=netmetrics earliest=-{minutes}m@m 
              | head {limit} 
              | eval _raw="Metric: " + metric_name + "=" + tostring(_value) + " (host=" + coalesce(host, "unknown") + ")", 
                     source="mpreview", 
                     index="netmetrics" ]
        | sort - _time
    """

    try:
        logs = check_events_from_splunk(
            start_time=f"-{minutes}m@m",
            url=url,
            user=user,
            password=password,
            query=query,
        )
        return logs or []
    except Exception as e:
        logger.error(f"Splunk query failed: {e}", exc_info=True)
        return []


# -----------------------------------------------------------
# Dump workflow logs
# -----------------------------------------------------------
@wait_for_splunk_data(timeout=60, interval=5)
def dump_splunk_workflow_logs(url, user, password, minutes=10, limit=5):

    logger.info("=" * 60)
    logger.info("SPLUNK WORKFLOW LOGS")
    logger.info("=" * 60)

    logs = get_recent_splunk_logs(
        url=url,
        user=user,
        password=password,
        minutes=minutes,
        limit=limit,
    )

    if not logs:
        logger.warning("No Splunk logs found")
    else:
        for i, log in enumerate(logs, 1):
            logger.info(f"{i}. {log}")

    logger.info("=" * 60)
    logger.info("END OF WORKFLOW LOGS")
    logger.info("=" * 60)


# -----------------------------------------------------------
# Auto dump on test failure
# -----------------------------------------------------------
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):

    outcome = yield
    report = outcome.get_result()

    if report.when != "call":
        return

    if report.failed:
        logger.warning("!" * 60)
        logger.warning("UI TEST FAILED - DUMPING SPLUNK WORKFLOW LOGS")
        logger.warning(f"Test: {item.nodeid}")
        logger.warning("!" * 60)

        host = item.config.getoption("--splunk-host", default=None)
        user = item.config.getoption("--splunk-user", default=None)
        password = item.config.getoption("--splunk-password", default=None)

        if not host or not user or not password:
            logger.warning("Splunk credentials not provided")
            return

        url = f"https://{host}:8089"

        dump_splunk_workflow_logs(
            url=url,
            user=user,
            password=password,
            minutes=10,
            limit=5,
        )
