import socket
from typing import Iterable, List, Mapping, Optional, Tuple, Union
from unittest import TestCase
from unittest.mock import ANY, Mock, patch
from urllib.parse import urlsplit

from pysnmp.proto import rfc1902
from pysnmp.smi import error
from requests import PreparedRequest, Response
from requests.adapters import BaseAdapter
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import RequestException
from urllib3.response import HTTPResponse

from splunk_connect_for_snmp.common.requests import CachedLimiterSession
from splunk_connect_for_snmp.snmp.manager import (
    MIB_INDEX,
    Poller,
    format_trap_varbind_value,
    is_mib_resolved,
)
from splunk_connect_for_snmp.snmp.mib_index_validator import MibIndexResponseValidator

parse_mib_index_impl = MibIndexResponseValidator.parse_mib_index


class _StaticResponseAdapter(BaseAdapter):
    def __init__(self, responses: Iterable[Union[Response, Exception]]) -> None:
        self._responses = iter(responses)
        self.sent_requests: List[PreparedRequest] = []

    def send(self, request: PreparedRequest, **kwargs) -> Response:
        self.sent_requests.append(request)
        response = next(self._responses)
        if isinstance(response, Exception):
            raise response
        response.request = request
        response.url = request.url
        response.raw = HTTPResponse(
            body=response.content,
            headers=response.headers,
            status=response.status_code,
            preload_content=False,
            request_method=request.method,
            request_url=request.url,
        )
        return response

    def close(self) -> None:
        pass


def _mib_index_response(
    content: str,
    *,
    status_code: int = 200,
    from_cache: bool = False,
    revalidated: bool = False,
    headers: Optional[Mapping[str, str]] = None,
) -> Response:
    response = Response()
    response.status_code = status_code
    response.encoding = "utf-8"
    response._content = content.encode(response.encoding)
    response.headers.update(headers or {})
    response.from_cache = from_cache
    response.revalidated = revalidated
    return response


def _mount_mib_index_adapter(session, adapter: _StaticResponseAdapter) -> None:
    session.mount(f"{urlsplit(MIB_INDEX).scheme}://", adapter)


def _poller_for_mib_refresh(session, *, cached: bool = True) -> Poller:
    poller = Poller.__new__(Poller)
    poller.mib_map = {}
    poller._uses_cached_mib_index_session = cached
    poller.session = session
    return poller


class TestMibIndexRefresh(TestCase):
    def _cached_limiter_session(
        self, responses: Iterable[Union[Response, Exception]]
    ) -> Tuple[CachedLimiterSession, _StaticResponseAdapter]:
        adapter = _StaticResponseAdapter(responses)
        session = CachedLimiterSession(
            per_second=120,
            backend="memory",
            expire_after=1800,
            stale_if_error=True,
            allowable_codes=[200],
        )
        self.addCleanup(session.close)
        _mount_mib_index_adapter(session, adapter)
        return session, adapter

    def _poller_with_response(
        self, response: Response, *, hook_calls: int = 1
    ) -> Poller:
        poller = _poller_for_mib_refresh(Mock())

        def get_mib_index(*args, **kwargs):
            for _ in range(hook_calls):
                kwargs["hooks"]["response"](response)
            return response

        poller.session.get.side_effect = get_mib_index
        return poller

    def test_live_response_is_parsed_once(self):
        index_content = "TEST-MIB,1.3.6.1.4.1.123\n"
        poller = self._poller_with_response(
            _mib_index_response(index_content), hook_calls=2
        )

        with patch.object(
            MibIndexResponseValidator,
            "parse_mib_index",
            wraps=parse_mib_index_impl,
        ) as parse_mib_index:
            refreshed = poller._refresh_mib_map(reason="startup")

        self.assertTrue(refreshed)
        self.assertEqual({"1.3.6.1.4.1.123": "TEST-MIB"}, poller.mib_map)
        parse_mib_index.assert_called_once_with(index_content)

    def test_cached_response_is_parsed_once(self):
        index_content = "TEST-MIB,1.3.6.1.4.1.123\n"
        response = _mib_index_response(index_content, from_cache=True)
        poller = self._poller_with_response(response)

        with patch.object(
            MibIndexResponseValidator,
            "parse_mib_index",
            wraps=parse_mib_index_impl,
        ) as parse_mib_index:
            refreshed = poller._refresh_mib_map(reason="startup")

        self.assertTrue(refreshed)
        parse_mib_index.assert_called_once_with(index_content)

    def test_uncached_response_is_parsed_once_without_cache_options(self):
        index_content = "TEST-MIB,1.3.6.1.4.1.123\n"
        poller = self._poller_with_response(_mib_index_response(index_content))
        poller._uses_cached_mib_index_session = False

        with patch.object(
            MibIndexResponseValidator,
            "parse_mib_index",
            wraps=parse_mib_index_impl,
        ) as parse_mib_index:
            refreshed = poller._refresh_mib_map(reason="startup")

        self.assertTrue(refreshed)
        parse_mib_index.assert_called_once_with(index_content)
        poller.session.get.assert_called_once_with(
            MIB_INDEX,
            hooks={"response": ANY},
        )
        request_options = poller.session.get.call_args.kwargs
        self.assertNotIn("refresh", request_options)
        self.assertNotIn("force_refresh", request_options)

    def test_equivalent_response_objects_reuse_the_parse_result(self):
        index_content = "TEST-MIB,1.3.6.1.4.1.123\n"
        first_response = _mib_index_response(index_content)
        returned_response = _mib_index_response(index_content)
        poller = self._poller_with_response(returned_response)

        def get_mib_index(*args, **kwargs):
            response_hook = kwargs["hooks"]["response"]
            response_hook(first_response)
            response_hook(returned_response)
            return returned_response

        poller.session.get.side_effect = get_mib_index

        with patch.object(
            MibIndexResponseValidator,
            "parse_mib_index",
            wraps=parse_mib_index_impl,
        ) as parse_mib_index:
            refreshed = poller._refresh_mib_map(reason="startup")

        self.assertTrue(refreshed)
        parse_mib_index.assert_called_once_with(index_content)

    def test_parse_result_is_not_retained_between_refreshes(self):
        index_content = "TEST-MIB,1.3.6.1.4.1.123\n"
        poller = self._poller_with_response(_mib_index_response(index_content))

        with patch.object(
            MibIndexResponseValidator,
            "parse_mib_index",
            wraps=parse_mib_index_impl,
        ) as parse_mib_index:
            first_refresh = poller._refresh_mib_map(reason="startup")
            second_refresh = poller._refresh_mib_map(reason="startup")

        self.assertTrue(first_refresh)
        self.assertTrue(second_refresh)
        self.assertEqual(2, parse_mib_index.call_count)

    def test_cached_limiter_session_live_response_is_parsed_once(self):
        index_content = "TEST-MIB,1.3.6.1.4.1.123\n"
        session, _ = self._cached_limiter_session([_mib_index_response(index_content)])

        poller = _poller_for_mib_refresh(session)

        with patch.object(
            MibIndexResponseValidator,
            "parse_mib_index",
            wraps=parse_mib_index_impl,
        ) as parse_mib_index:
            refreshed = poller._refresh_mib_map(reason="startup")

        self.assertTrue(refreshed)
        parse_mib_index.assert_called_once_with(index_content)

    def test_changed_etag_replaces_cached_mib_index(self):
        first_content = "FIRST-MIB,1.3.6.1.4.1.111\n"
        second_content = "SECOND-MIB,1.3.6.1.4.1.222\n"
        session, adapter = self._cached_limiter_session(
            [
                _mib_index_response(first_content, headers={"ETag": '"v1"'}),
                _mib_index_response(second_content, headers={"ETag": '"v2"'}),
            ]
        )
        session.get(MIB_INDEX)

        poller = _poller_for_mib_refresh(session)

        refreshed = poller._refresh_mib_map(reason="startup")

        self.assertTrue(refreshed)
        self.assertEqual({"1.3.6.1.4.1.222": "SECOND-MIB"}, poller.mib_map)
        self.assertEqual('"v1"', adapter.sent_requests[1].headers["If-None-Match"])

        cached_response = session.get(MIB_INDEX, only_if_cached=True)
        self.assertTrue(cached_response.from_cache)
        self.assertEqual(second_content, cached_response.text)
        self.assertEqual('"v2"', cached_response.headers["ETag"])
        self.assertEqual(2, len(adapter.sent_requests))

    def test_network_failure_returns_last_good_cached_index(self):
        first_content = "FIRST-MIB,1.3.6.1.4.1.111\n"
        session, adapter = self._cached_limiter_session(
            [
                _mib_index_response(first_content, headers={"ETag": '"v1"'}),
                RequestsConnectionError("mibserver unavailable"),
            ]
        )
        session.get(MIB_INDEX)

        poller = _poller_for_mib_refresh(session)

        refreshed = poller._refresh_mib_map(reason="startup")

        self.assertTrue(refreshed)
        self.assertEqual({"1.3.6.1.4.1.111": "FIRST-MIB"}, poller.mib_map)

        cached_response = session.get(MIB_INDEX, only_if_cached=True)
        self.assertTrue(cached_response.from_cache)
        self.assertEqual(first_content, cached_response.text)
        self.assertEqual(2, len(adapter.sent_requests))

    def test_http_503_returns_last_good_cached_index(self):
        first_content = "FIRST-MIB,1.3.6.1.4.1.111\n"
        session, adapter = self._cached_limiter_session(
            [
                _mib_index_response(first_content, headers={"ETag": '"v1"'}),
                _mib_index_response("temporarily unavailable", status_code=503),
            ]
        )
        session.get(MIB_INDEX)

        poller = _poller_for_mib_refresh(session)

        with self.assertLogs(
            "splunk_connect_for_snmp.snmp.manager", level="WARNING"
        ) as captured_logs:
            refreshed = poller._refresh_mib_map(reason="startup")

        self.assertTrue(refreshed)
        self.assertEqual({"1.3.6.1.4.1.111": "FIRST-MIB"}, poller.mib_map)
        self.assertTrue(
            any(
                "Live MIB index could not be confirmed during the startup refresh"
                in message
                for message in captured_logs.output
            )
        )

        cached_response = session.get(MIB_INDEX, only_if_cached=True)
        self.assertTrue(cached_response.from_cache)
        self.assertEqual(first_content, cached_response.text)
        self.assertEqual(2, len(adapter.sent_requests))

    def test_cached_limiter_session_invalid_live_response_keeps_cached_index(self):
        cached_content = "CACHED-MIB,1.3.6.1.4.1.456\n"
        session, _ = self._cached_limiter_session(
            [
                _mib_index_response(cached_content, headers={"ETag": '"cached-index"'}),
                _mib_index_response("invalid-row\n"),
            ]
        )
        session.get(MIB_INDEX)

        poller = _poller_for_mib_refresh(session)

        with patch.object(
            MibIndexResponseValidator,
            "parse_mib_index",
            wraps=parse_mib_index_impl,
        ) as parse_mib_index:
            refreshed = poller._refresh_mib_map(reason="startup")

        self.assertTrue(refreshed)
        self.assertEqual({"1.3.6.1.4.1.456": "CACHED-MIB"}, poller.mib_map)
        self.assertEqual(2, parse_mib_index.call_count)

        cached_response = session.get(MIB_INDEX)
        self.assertTrue(cached_response.from_cache)
        self.assertEqual(cached_content, cached_response.text)

    def test_cached_limiter_session_revalidated_response_is_parsed_once(self):
        cached_content = "CACHED-MIB,1.3.6.1.4.1.456\n"
        session, _ = self._cached_limiter_session(
            [
                _mib_index_response(cached_content, headers={"ETag": '"cached-index"'}),
                _mib_index_response("", status_code=304),
            ]
        )
        session.get(MIB_INDEX)

        poller = _poller_for_mib_refresh(session)

        with patch.object(
            MibIndexResponseValidator,
            "parse_mib_index",
            wraps=parse_mib_index_impl,
        ) as parse_mib_index:
            refreshed = poller._refresh_mib_map(reason="startup")

        self.assertTrue(refreshed)
        self.assertEqual({"1.3.6.1.4.1.456": "CACHED-MIB"}, poller.mib_map)
        parse_mib_index.assert_called_once_with(cached_content)

    def test_stale_fallback_is_parsed_when_live_response_differs(self):
        live_response = _mib_index_response("invalid-row\n")
        cached_content = "CACHED-MIB,1.3.6.1.4.1.456\n"
        cached_response = _mib_index_response(cached_content, from_cache=True)
        poller = self._poller_with_response(cached_response)

        def get_mib_index(*args, **kwargs):
            try:
                kwargs["hooks"]["response"](live_response)
            except RequestException:
                return cached_response
            raise AssertionError("Invalid live response was not rejected")

        poller.session.get.side_effect = get_mib_index

        with patch.object(
            MibIndexResponseValidator,
            "parse_mib_index",
            wraps=parse_mib_index_impl,
        ) as parse_mib_index:
            refreshed = poller._refresh_mib_map(reason="startup")

        self.assertTrue(refreshed)
        self.assertEqual({"1.3.6.1.4.1.456": "CACHED-MIB"}, poller.mib_map)
        self.assertEqual(2, parse_mib_index.call_count)

    def test_invalid_live_response_preserves_existing_map(self):
        poller = self._poller_with_response(_mib_index_response("invalid-row\n"))
        existing_map = {"1.3.6.1.4.1.789": "EXISTING-MIB"}
        poller.mib_map = existing_map

        with patch.object(
            MibIndexResponseValidator,
            "parse_mib_index",
            wraps=parse_mib_index_impl,
        ) as parse_mib_index:
            refreshed = poller._refresh_mib_map(reason="startup")

        self.assertFalse(refreshed)
        self.assertIs(existing_map, poller.mib_map)
        parse_mib_index.assert_called_once_with("invalid-row\n")

    def test_non_success_response_is_not_parsed(self):
        response = _mib_index_response("unavailable", status_code=503)
        poller = self._poller_with_response(response)

        with patch.object(
            MibIndexResponseValidator,
            "parse_mib_index",
            wraps=parse_mib_index_impl,
        ) as parse_mib_index:
            refreshed = poller._refresh_mib_map(reason="startup")

        self.assertFalse(refreshed)
        parse_mib_index.assert_not_called()


class TestMibProcessing(TestCase):
    def test_format_trap_varbind_value_ipv4_octets(self):
        octets = rfc1902.OctetString(socket.inet_aton("10.1.1.1"))
        self.assertEqual("10.1.1.1", format_trap_varbind_value(octets))

    def test_format_trap_varbind_value_ipv6_octets(self):
        octets = rfc1902.OctetString(socket.inet_pton(socket.AF_INET6, "2001:db8::1"))
        self.assertEqual("2001:db8::1", format_trap_varbind_value(octets))

    def test_format_trap_varbind_value_keeps_pretty_print(self):
        self.assertEqual("3", format_trap_varbind_value(rfc1902.Integer(3)))

    def test_format_trap_varbind_value_genuine_ipaddress(self):
        self.assertEqual(
            "10.1.1.1", format_trap_varbind_value(rfc1902.IpAddress("10.1.1.1"))
        )

    def test_format_trap_varbind_value_printable_4char_kept_as_text(self):
        self.assertEqual("TEST", format_trap_varbind_value(rfc1902.OctetString("TEST")))

    def test_format_trap_varbind_value_printable_16char_kept_as_text(self):
        text = "abcdefghijklmnop"  # 16 printable bytes
        self.assertEqual(text, format_trap_varbind_value(rfc1902.OctetString(text)))

    def test_format_trap_varbind_value_binary_falls_back_to_hex(self):
        octets = rfc1902.OctetString(hexValue="00ff10")  # 3 binary bytes
        self.assertEqual("0x00ff10", format_trap_varbind_value(octets))

    def test_load_mib(self):
        poller = Poller.__new__(Poller)
        poller.builder = Mock()
        loaded = poller.load_mibs(["a", "b", "c"])
        calls = poller.builder.load_modules.call_args_list

        self.assertEqual({"a", "b", "c"}, loaded)
        self.assertEqual("a", calls[0][0][0])
        self.assertEqual("b", calls[1][0][0])
        self.assertEqual("c", calls[2][0][0])

    def test_load_mib_returns_only_successful(self):
        poller = Poller.__new__(Poller)
        poller.builder = Mock()
        poller.builder.load_modules.side_effect = [
            None,
            error.MibLoadError(),
            None,
        ]
        loaded = poller.load_mibs(["a", "b", "c"])
        self.assertEqual({"a", "c"}, loaded)

    def test_is_mib_known_when_mib_map_is_empty(self):
        poller = Poller.__new__(Poller)
        poller.mib_map = {}
        found, mib = poller.is_mib_known("some ID", "1.2.3.4.5.6", "address")

        self.assertFalse(found)
        self.assertEqual(mib, "")

    def test_is_mib_known(self):
        poller = Poller.__new__(Poller)
        poller.mib_map = {"1.2.3.4.5.6": "test1"}
        found, mib = poller.is_mib_known("some ID", "1.2.3.4.5.6.7", "address")

        self.assertTrue(found)
        self.assertEqual("test1", mib)

    def test_is_mib_known_prefix_limit(self):
        poller = Poller.__new__(Poller)
        poller.mib_map = {"1.2.3.4.5": "test1"}
        found, mib = poller.is_mib_known("some ID", "1.2.3.4.5.6.7", "address")

        self.assertFalse(found)
        self.assertEqual(mib, "")

    def test_is_mib_resolved(self):
        self.assertFalse(is_mib_resolved("RFC1213-MIB::"))
        self.assertFalse(is_mib_resolved("SNMPv2-SMI::enterprises."))
        self.assertFalse(is_mib_resolved("SNMPv2-SMI::mib-2"))
        self.assertTrue(is_mib_resolved("OTHER"))

    def test_exception_during_loading(self):
        poller = Poller.__new__(Poller)
        poller.builder = Mock()
        poller.builder.load_modules.side_effect = error.MibLoadError()
        loaded = poller.load_mibs(["a"])
        self.assertEqual(set(), loaded)

    def test_find_new_mibs_is_found(self):
        poller = Poller.__new__(Poller)
        poller.is_mib_known = Mock()
        poller.is_mib_known.return_value = (True, "SNMPv2-SMI")
        remote_mib = ["SNMPv2-SMI"]
        found = poller.find_new_mibs("1.3.6.1.3.4", remote_mib, "address", "some ID")

        self.assertTrue(found)
        self.assertEqual(remote_mib, ["SNMPv2-SMI"])

    def test_find_new_mibs_add_new(self):
        poller = Poller.__new__(Poller)
        poller.is_mib_known = Mock()
        poller.is_mib_known.return_value = (False, "SNMPv2-SMI")
        remote_mib = ["RFC1213-MIB"]
        found = poller.find_new_mibs("1.3.6.1.3.4", remote_mib, "address", "some ID")

        self.assertEqual(remote_mib, ["RFC1213-MIB", "SNMPv2-SMI"])
        self.assertFalse(found)
