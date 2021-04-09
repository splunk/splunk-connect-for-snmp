import pytest
import splunklib.client as client
import time
import logging

logger = logging.getLogger(__name__)


def pytest_addoption(parser):
    parser.addoption(
        "--splunk_host",
        action="store",
        dest="splunk_host",
        default="127.0.0.1",
        help="Address of the Splunk Server",
    )
    parser.addoption(
        "--trap_external_ip",
        action="store",
        dest="trap_external_ip",
        default="127.0.0.1",
        help="Trap Kubernets external IP",
    )
    parser.addoption(
        "--splunk_port",
        action="store",
        dest="splunk_port",
        default="8089",
        help="Splunk rest port",
    )
    parser.addoption(
        "--splunk_user",
        action="store",
        dest="splunk_user",
        default="admin",
        help="Splunk login user",
    )
    parser.addoption(
        "--splunk_password",
        action="store",
        dest="splunk_password",
        default="12345678",
        help="Splunk password",
    )


@pytest.fixture(scope="session")
def setup_splunk(request):
    tried = 0
    while True:
        try:
            username = request.config.getoption("splunk_user")
            password = request.config.getoption("splunk_password")
            hostname = request.config.getoption("splunk_host")
            port = request.config.getoption("splunk_port")
            service = client.connect(
                username=username, password=password, host=hostname, port=port
            )
            break
        except ConnectionRefusedError:
            logger.error("Connection error!")
            tried += 1
            if tried > 600:
                raise
            time.sleep(1)
    return service
