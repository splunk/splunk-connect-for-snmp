import os
from datetime import datetime
import json

import pytest
import splunklib.client as client
import splunklib.results as results
from logger.logger import Logger
from webdriver.webriver_factory import WebDriverFactory

from splunk_search import check_events_from_splunk

logger = Logger().get_logger()


def get_splunk_internal_logs(url, user, password, minutes=5):
    query = (
        'search index=_internal '
        '(log_level=ERROR OR log_level=WARN)'
    )

    try:
        return check_events_from_splunk(
            start_time=f"-{minutes}m@m",
            url=url,
            user=user,
            password=password,
            query=query,
        )
    except Exception as e:
        return [{
            "error": f"Splunk query failed: {str(e)}"
        }]


def filter_and_format_logs(logs):
    """
    Filter repetitive logs and format for readability.
    Shows: All ERRORS + unique WARNs (grouped)
    """
    if not logs:
        return []
    
    errors = []
    warn_groups = {}
    
    for log in logs:
        # Handle error responses
        if "error" in log and "Splunk query failed" in str(log.get("error", "")):
            return [log]
        
        log_level = log.get('log_level', 'UNKNOWN')
        
        # 🔥 ALWAYS show ERRORs
        if log_level == 'ERROR':
            errors.append(log)
        
        # 🔥 Group WARNs by message type
        elif log_level == 'WARN':
            try:
                raw = log.get('_raw', '')
                if raw:
                    data = json.loads(raw)
                    message = data.get('message', 'Unknown')
                    
                    # Group similar warnings
                    if message not in warn_groups:
                        warn_groups[message] = {
                            'count': 0,
                            'first_log': log,
                            'message': message
                        }
                    warn_groups[message]['count'] += 1
            except:
                # If parsing fails, show the raw log
                if 'Unknown' not in warn_groups:
                    warn_groups['Unknown'] = {'count': 0, 'first_log': log, 'message': 'Unknown'}
                warn_groups['Unknown']['count'] += 1
    
    return errors, warn_groups


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


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    if report.when != "call":
        return

    if report.failed:
        print("\n========== UI TEST FAILURE DEBUG ==========")
        print(f"Test failed: {item.nodeid}")

        try:
            config = item.config
            
            if not config.getoption("--splunk-host", default=None):
                print("⚠ Splunk configuration not provided")
                return

            host = config.getoption("--splunk-host")
            url = f"https://{host}:8089"
            user = config.getoption("--splunk-user")
            password = config.getoption("--splunk-password")

            print("\n--- Splunk _internal Logs (last 10 min) ---")

            logs = get_splunk_internal_logs(
                url=url,
                user=user,
                password=password,
                minutes=10,
            )

            if not logs:
                print("ℹ️ No Splunk ERROR/WARN logs found")
                return
            
            # 🔥 FILTER AND FORMAT LOGS
            result = filter_and_format_logs(logs)
            
            # Handle error case
            if isinstance(result, list) and len(result) == 1 and "error" in result[0]:
                print(f"❌ {result[0]['error']}")
                return
            
            errors, warn_groups = result
            
            # 🔥 SHOW ERRORS (full detail)
            if errors:
                print(f"\n🔴 ERRORS ({len(errors)} found):")
                for err in errors:
                    try:
                        raw = json.loads(err.get('_raw', '{}'))
                        print(f"  • {raw.get('time', 'N/A')} - {raw.get('message', 'No message')}")
                        if 'error' in raw:
                            print(f"    Error: {raw['error']}")
                    except:
                        print(f"  • {err.get('_time', 'N/A')} - {err.get('_raw', 'Unknown error')[:100]}")
            
            # 🔥 SHOW WARNINGS (grouped summary)
            if warn_groups:
                print(f"\n⚠️  WARNINGS (grouped, {sum(g['count'] for g in warn_groups.values())} total):")
                for msg, group in sorted(warn_groups.items(), key=lambda x: x[1]['count'], reverse=True):
                    print(f"  • [{group['count']}x] {msg[:80]}")
            
            if not errors and not warn_groups:
                print("ℹ️ No significant logs found")

        except Exception as e:
            print(f"❌ Splunk internal log capture failed: {e}")
