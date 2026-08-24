from unittest import TestCase
from unittest.mock import MagicMock, patch

from splunk_connect_for_snmp.snmp.manager import Poller


class TestMibMapStartupRefresh(TestCase):
    """
    A worker builds its OID-to-MIB lookup table (mib_map) once, at startup, from the
    mibserver's index.csv. That fetch goes through a MongoDB-backed HTTP cache
    (expire_after=1800), so the startup fetch conditionally revalidates the cached
    index with mibserver instead of blindly trusting the 30-minute TTL - while still
    falling back to the last good cached index (stale_if_error) if mibserver is
    briefly unreachable. See docs/mib-request.md "Use MIB server with local MIBs".
    """

    @patch("pymongo.MongoClient", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.ProfilesManager", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.SnmpEngine", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.compiler.addMibCompiler", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.view.MibViewController", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.MongoCache", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.CachedLimiterSession")
    def test_startup_index_fetch_revalidates_cache(self, mock_session_cls):
        mock_session = mock_session_cls.return_value
        mock_session.get.return_value = MagicMock(status_code=200, text="MOD,1.2.3\n")

        Poller()

        mock_session.get.assert_called_once()
        args, kwargs = mock_session.get.call_args
        self.assertTrue(
            kwargs.get("refresh"),
            "startup index.csv fetch must pass refresh=True so a restarted worker "
            "conditionally revalidates the cached index with mibserver instead of "
            "trusting it for the full 30-minute TTL, while still tolerating a "
            "transient mibserver outage via stale_if_error",
        )

    @patch("pymongo.MongoClient", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.ProfilesManager", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.SnmpEngine", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.compiler.addMibCompiler", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.view.MibViewController", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.Session")
    def test_no_mongo_startup_fetch_omits_refresh(self, mock_session_cls):
        # no_mongo=True (used by the CLI walk entrypoint) uses a plain requests.Session,
        # which has no cache to revalidate and does not accept refresh as a kwarg.
        mock_session = mock_session_cls.return_value
        mock_session.get.return_value = MagicMock(status_code=200, text="MOD,1.2.3\n")

        Poller(no_mongo=True)

        mock_session.get.assert_called_once()
        args, kwargs = mock_session.get.call_args
        self.assertNotIn("refresh", kwargs)
