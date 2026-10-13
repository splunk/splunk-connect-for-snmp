import pytest

from splunk_connect_for_snmp.common import common


@pytest.fixture(autouse=True)
def reset_shared_mongo_client():
    # The per-process client is cached globally; don't let one test's mock leak into the next.
    common._mongo_client = None
    common._mongo_client_pid = None
    yield
    common.close_mongo_client()
