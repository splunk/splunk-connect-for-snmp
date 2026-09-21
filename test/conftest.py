import pytest

from splunk_connect_for_snmp.common.mongo_client import reset_mongo_client


@pytest.fixture(autouse=True)
def _reset_mongo_client():
    """Prevent the process-wide MongoClient singleton from leaking across tests.

    Without this, whichever test runs first "wins" the cached client - e.g. a
    test that patches pymongo.MongoClient would cache a MagicMock that a later
    test expecting a real Collection object would then incorrectly receive.
    """
    reset_mongo_client()
    yield
    reset_mongo_client()
