import os


def get_execution_type():
    execution_type = os.environ.get("CI_EXECUTION_TYPE")
    if execution_type is None:
        return EXECUTION_TYPE_LOCAL
    else:
        return execution_type


def get_ui_host_ip_address():
    if EXECUTION_TYPE != EXECUTION_TYPE_LOCAL:
        # test executed in pipeline in GitHub actions so the UI is on the same VM where tests are executed
        return "localhost"
    else:
        return UI_HOST_FOR_LOCAL_EXECUTION


EXECUTION_TYPE_LOCAL = "local"
EXECUTION_TYPE = get_execution_type()

UI_HOST_FOR_LOCAL_EXECUTION = "PUT_HERE_IP_ADDRESS_OF_SC4SNMP_VM"
UI_HOST = get_ui_host_ip_address()
UI_URL = f"http://{UI_HOST}:30001/"
EVENT_INDEX = "netops"
LOGS_INDEX = "em_logs"

# timers
IMPLICIT_WAIT_TIMER = 10

# yaml file
YAML_FILE_PATH = "./../integration_tests/values.yaml"
DEFAULT_PORT = 161
