import pytest

from splunk_connect_for_snmp.common.mongo_client import reset_mongo_client


@pytest.fixture(autouse=True)
def _reset_mongo_client_singleton():
    reset_mongo_client()
    yield
    reset_mongo_client()
