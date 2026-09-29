from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, call, patch

from celery.exceptions import Retry
from pysnmp.smi import error

from splunk_connect_for_snmp.snmp.manager import (
    DEFAULT_STANDARD_MIBS,
    PYSNMP_PROTOCOL_MIBS,
    MibIndexUnavailable,
    Poller,
)


class TestPollerInitialization(TestCase):
    """
    The task is constructed in the prefork parent and loads its MIB index only
    when it first runs in a child. The cached fetch revalidates index.csv and
    can fall back to the last good response during a brief outage.
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
    def test_first_task_index_fetch_revalidates_cache(self, mock_session_cls):
        mock_session = mock_session_cls.return_value
        mock_session.get.return_value = MagicMock(status_code=200, text="MOD,1.2.3\n")

        poller = Poller()
        mock_session_cls.assert_not_called()
        poller._ensure_worker_initialized()
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
    def test_no_mongo_first_use_fetch_omits_refresh(self, mock_session_cls):
        # no_mongo=True (used by the CLI walk entrypoint) uses a plain requests.Session,
        # which has no cache to revalidate and does not accept refresh as a kwarg.
        mock_session = mock_session_cls.return_value
        mock_session.get.return_value = MagicMock(status_code=200, text="MOD,1.2.3\n")

        poller = Poller(no_mongo=True)
        mock_session_cls.assert_not_called()
        poller._ensure_worker_initialized()

        mock_session.get.assert_called_once()
        args, kwargs = mock_session.get.call_args
        self.assertNotIn("refresh", kwargs)

    def test_index_bootstrap_retry_reuses_mib_builder(self):
        with (
            patch("splunk_connect_for_snmp.snmp.manager.get_mongo_client", MagicMock()),
            patch("splunk_connect_for_snmp.snmp.manager.ProfilesManager", MagicMock()),
            patch(
                "splunk_connect_for_snmp.snmp.manager.builder.MibBuilder"
            ) as builder_cls,
            patch("splunk_connect_for_snmp.snmp.manager.view.MibViewController"),
            patch("splunk_connect_for_snmp.snmp.manager.compiler.add_mib_compiler"),
            patch("splunk_connect_for_snmp.snmp.manager.MongoCache"),
            patch(
                "splunk_connect_for_snmp.snmp.manager.CachedLimiterSession"
            ) as session_cls,
        ):
            poller = Poller()
            with patch.object(
                poller, "_refresh_mib_map", side_effect=[False, True]
            ) as refresh:
                with self.assertRaises(MibIndexUnavailable):
                    poller._ensure_worker_initialized()
                self.assertIsNone(poller._initialized_pid)
                self.assertIsNotNone(poller._mib_initialized_pid)

                poller._ensure_worker_initialized()

            builder_cls.assert_called_once_with()
            self.assertEqual(
                [call(*PYSNMP_PROTOCOL_MIBS)]
                + [call(mib) for mib in DEFAULT_STANDARD_MIBS],
                builder_cls.return_value.load_modules.call_args_list,
            )
            self.assertEqual(2, refresh.call_count)
            self.assertEqual(2, session_cls.call_count)
            self.assertEqual(poller._mib_initialized_pid, poller._initialized_pid)

    def test_failed_index_fetch_retries_without_changing_snmp_retry_limit(self):
        poller = Poller()
        poller.name = "test.poller"
        poller.max_retries = 5
        poller.request_stack = SimpleNamespace(top=SimpleNamespace(retries=0))

        def schedule_retry(**_):
            poller.override_max_retries = 1_000_000
            raise Retry("scheduled")

        with (
            patch.object(
                poller,
                "_ensure_worker_initialized",
                side_effect=MibIndexUnavailable("index unavailable"),
            ),
            patch.object(poller, "retry", side_effect=schedule_retry) as retry,
        ):
            with self.assertRaises(Retry):
                poller.before_start("task-id", (), {})

        self.assertEqual(5, retry.call_args.kwargs["countdown"])
        self.assertEqual(1_000_000, retry.call_args.kwargs["max_retries"])
        self.assertEqual(5, poller.max_retries)
        self.assertNotIn("override_max_retries", poller.__dict__)

    def test_missing_standard_mib_retries_before_start(self):
        poller = Poller()
        poller.name = "test.poller"
        poller.request_stack = SimpleNamespace(top=SimpleNamespace(retries=0))
        missing_mib = error.MibNotFoundError("standard MIB unavailable")

        with (
            patch(
                "splunk_connect_for_snmp.snmp.manager.builder.MibBuilder"
            ) as builder_cls,
            patch("splunk_connect_for_snmp.snmp.manager.view.MibViewController"),
            patch("splunk_connect_for_snmp.snmp.manager.compiler.add_mib_compiler"),
            patch.object(poller, "retry", side_effect=Retry("scheduled")) as retry,
        ):
            builder_cls.return_value.load_modules.side_effect = [None, missing_mib]
            with self.assertRaises(Retry):
                poller.before_start("task-id", (), {})

        self.assertIs(retry.call_args.kwargs["exc"], missing_mib)
        self.assertEqual(5, retry.call_args.kwargs["countdown"])
        self.assertEqual(1_000_000, retry.call_args.kwargs["max_retries"])
        self.assertIsNone(poller._mib_initialized_pid)
        self.assertIsNone(poller._initialized_pid)
