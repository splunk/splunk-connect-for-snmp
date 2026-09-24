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

    @patch("splunk_connect_for_snmp.snmp.manager.get_mongo_client", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.ProfilesManager", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.SnmpEngine", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.builder.MibBuilder", MagicMock())
    @patch(
        "splunk_connect_for_snmp.snmp.manager.compiler.add_mib_compiler", MagicMock()
    )
    @patch("splunk_connect_for_snmp.snmp.manager.view.MibViewController", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.MongoCache", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.CachedLimiterSession")
    def test_startup_index_fetch_revalidates_cache(self, mock_session_cls):
        mock_session = mock_session_cls.return_value
        mock_session.get.return_value = MagicMock(status_code=200, text="MOD,1.2.3\n")

        poller = Poller()
        poller._ensure_worker_initialized()

        mock_session.get.assert_called_once()
        args, kwargs = mock_session.get.call_args
        self.assertTrue(
            kwargs.get("refresh"),
            "startup index.csv fetch must pass refresh=True so a restarted worker "
            "conditionally revalidates the cached index with mibserver instead of "
            "trusting it for the full 30-minute TTL, while still tolerating a "
            "transient mibserver outage via stale_if_error",
        )

    @patch("splunk_connect_for_snmp.snmp.manager.get_mongo_client", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.ProfilesManager", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.SnmpEngine", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.builder.MibBuilder", MagicMock())
    @patch(
        "splunk_connect_for_snmp.snmp.manager.compiler.add_mib_compiler", MagicMock()
    )
    @patch("splunk_connect_for_snmp.snmp.manager.view.MibViewController", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.Session")
    def test_no_mongo_startup_fetch_omits_refresh(self, mock_session_cls):
        # no_mongo=True (used by the CLI walk entrypoint) uses a plain requests.Session,
        # which has no cache to revalidate and does not accept refresh as a kwarg.
        mock_session = mock_session_cls.return_value
        mock_session.get.return_value = MagicMock(status_code=200, text="MOD,1.2.3\n")

        poller = Poller(no_mongo=True)
        poller._ensure_worker_initialized()

        mock_session.get.assert_called_once()
        args, kwargs = mock_session.get.call_args
        self.assertNotIn("refresh", kwargs)


class TestBeforeStartTriggersWorkerInit(TestCase):
    """
    walk/poll/trap all use Poller as their Celery task base. before_start is a
    Celery task handler that runs in the worker child, after the prefork pool
    has forked - the first safe point to touch Mongo - so it is the single
    trigger point for the lazy bootstrap, rather than each task body calling it.
    """

    @patch("splunk_connect_for_snmp.snmp.manager.get_mongo_client", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.ProfilesManager", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.SnmpEngine", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.builder.MibBuilder", MagicMock())
    @patch(
        "splunk_connect_for_snmp.snmp.manager.compiler.add_mib_compiler", MagicMock()
    )
    @patch("splunk_connect_for_snmp.snmp.manager.view.MibViewController", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.Poller._ensure_worker_initialized")
    def test_before_start_delegates_to_ensure_worker_initialized(self, m_ensure_init):
        poller = Poller(no_mongo=True)

        poller.before_start("task-id", (), {})

        m_ensure_init.assert_called_once()


class TestWorkerInitFailureIsVisibleAndSelfHeals(TestCase):
    """
    If Mongo/mibserver is unreachable at worker startup, the lazy bootstrap
    fails inside a normal task (via before_start), so Celery's ordinary
    task-failure handling makes it visible - it is not silently swallowed the
    way an exception raised from a worker_process_init signal receiver would
    be. Because the guard flag is only set on success, a later task on the
    same worker retries the bootstrap and the worker self-heals once
    Mongo/mibserver becomes reachable again.
    """

    @patch("splunk_connect_for_snmp.snmp.manager.get_mongo_client", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.ProfilesManager", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.SnmpEngine", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.builder.MibBuilder", MagicMock())
    @patch(
        "splunk_connect_for_snmp.snmp.manager.compiler.add_mib_compiler", MagicMock()
    )
    @patch("splunk_connect_for_snmp.snmp.manager.view.MibViewController", MagicMock())
    @patch("splunk_connect_for_snmp.snmp.manager.Poller._refresh_mib_map")
    def test_failed_bootstrap_raises_and_a_later_success_self_heals(
        self, m_refresh_mib_map
    ):
        poller = Poller(no_mongo=True)

        m_refresh_mib_map.return_value = False
        with self.assertRaises(RuntimeError):
            poller._ensure_worker_initialized()
        self.assertFalse(poller._worker_initialized)

        m_refresh_mib_map.return_value = True
        poller._ensure_worker_initialized()
        self.assertTrue(poller._worker_initialized)
