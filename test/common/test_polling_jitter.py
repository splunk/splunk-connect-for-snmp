import runpy
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from splunk_connect_for_snmp.common import polling_jitter
from splunk_connect_for_snmp.common.common import positive_integer
from splunk_connect_for_snmp.common.polling_jitter import (
    JitterSettings,
    PollingJitterError,
    calculate_offset,
    canonical_identity,
    first_due,
)

UTC = timezone.utc
NOW = datetime(2026, 1, 1, 12, tzinfo=UTC)


def read_settings(environment):
    with patch(
        "os.getenv", side_effect=lambda key, default=None: environment.get(key, default)
    ):
        return runpy.run_path(polling_jitter.__file__)["JITTER_SETTINGS"]


def test_settings_are_read_once(monkeypatch):
    original = polling_jitter.JITTER_SETTINGS
    monkeypatch.setenv(
        "POLLING_JITTER_ENABLED", "true" if not original.enabled else "false"
    )
    monkeypatch.setenv("POLLING_JITTER_WINDOW_SECONDS", "10")
    assert polling_jitter.JITTER_SETTINGS is original


@pytest.mark.parametrize(
    "value,expected",
    [
        ("true", True),
        ("TRUE", True),
        ("TrUe", True),
        ("false", False),
        ("FALSE", False),
        ("1", True),
        ("yes", True),
        ("Y", True),
        ("t", True),
        ("0", False),
        ("no", False),
        ("N", False),
        ("f", False),
    ],
)
def test_boolean_environment(value, expected):
    assert read_settings({"POLLING_JITTER_ENABLED": value}).enabled is expected


def test_absent_settings():
    settings = read_settings({})
    assert (settings.enabled, settings.window_seconds) == (False, 60)


@pytest.mark.parametrize("value", ["", " true ", "invalid"])
def test_unrecognized_enablement_defaults_to_false(value):
    assert read_settings({"POLLING_JITTER_ENABLED": value}).enabled is False


@pytest.mark.parametrize("enabled", ["false", "true"])
@pytest.mark.parametrize("value", ["1", "10", "60", "86400"])
def test_valid_window(enabled, value):
    assert read_settings(
        {"POLLING_JITTER_ENABLED": enabled, "POLLING_JITTER_WINDOW_SECONDS": value}
    ).window_seconds == int(value)


@pytest.mark.parametrize("enabled", ["false", "true"])
@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
        1.5,
        True,
        False,
        None,
        "",
        "0",
        "-1",
        "1.0",
        "1e2",
        "true",
        "false",
        "invalid",
        "86401",
        " 60 ",
        "+60",
        "\u0666\u0660",
        "\uff16\uff10",
    ],
)
def test_invalid_window_even_when_disabled(enabled, value):
    with pytest.raises(ValueError, match="POLLING_JITTER_WINDOW_SECONDS") as error:
        read_settings(
            {"POLLING_JITTER_ENABLED": enabled, "POLLING_JITTER_WINDOW_SECONDS": value}
        )
    assert type(error.value) is ValueError


@pytest.mark.parametrize(
    "value", [0, -1, 0.5, 1.0, True, False, None, "", "1.5", "-2", "invalid"]
)
def test_invalid_interval(value):
    with pytest.raises(ValueError, match="Polling interval"):
        calculate_offset("router-01", 161, value, "poll", JitterSettings(True))


@pytest.mark.parametrize(
    "address,normalized",
    [
        ("192.0.2.1", "192.0.2.1"),
        ("2001:0db8:0000::1", "2001:db8::1"),
        (" ROUTER-01 ", "router-01"),
    ],
)
@pytest.mark.parametrize("port", [1, 161, 65535])
def test_canonical_identity(address, normalized, port):
    with patch("socket.getaddrinfo", side_effect=AssertionError("No DNS lookup")):
        assert (
            canonical_identity(address, port, 60, "poll")
            == f"v1|poll|{normalized}|{port}|60"
        )


@pytest.mark.parametrize(
    "address",
    [
        "",
        " ",
        "bad|address",
        "router\n",
        "router\t",
        "a\x00b",
        "router\u200b",
        "bad host",
        "not:ipv6",
    ],
)
def test_invalid_address_does_not_echo_input(address):
    with pytest.raises(
        PollingJitterError, match="Invalid jitter device address"
    ) as error:
        canonical_identity(address, 161, 60, "poll")
    assert str(error.value) == "Invalid jitter device address"


@pytest.mark.parametrize("port", [0, -1, 65536, True, 1.5, "bad"])
def test_invalid_port(port):
    with pytest.raises(ValueError, match="SNMP port"):
        canonical_identity("router-01", port, 60, "poll")


@pytest.mark.parametrize("kind", ["enrich", "discovery", "trap", "WALK", "", None])
def test_only_walk_and_poll_identities(kind):
    with pytest.raises(PollingJitterError, match="task type"):
        canonical_identity("router-01", 161, 60, kind)


@pytest.mark.parametrize("interval,offset", [(60, 42), (300, 56)])
def test_fixed_vectors(interval, offset):
    actual, fingerprint = calculate_offset(
        "router-01", 161, interval, "poll", JitterSettings(True)
    )
    assert actual == offset
    assert fingerprint.startswith("sha256-v1:60:")
    assert len(fingerprint.rsplit(":", 1)[1]) == 64
    assert first_due(NOW + timedelta(seconds=interval), actual) == NOW + timedelta(
        seconds=interval + offset
    )


def test_ten_600_second_poll_vectors():
    offsets = [
        calculate_offset(f"router-{i:02}", 161, 600, "poll", JitterSettings(True))[0]
        for i in range(1, 11)
    ]
    assert offsets == [22, 38, 49, 17, 16, 43, 24, 22, 51, 50]
    assert offsets[0] == offsets[7]  # A collision is valid.


def test_repeatability_and_changed_identity():
    args = ("router-01", 161, 60, "poll")
    original = calculate_offset(*args, JitterSettings(True))
    assert calculate_offset(*args, JitterSettings(True)) == original
    for changed in [
        ("router-02", 161, 60, "poll"),
        ("router-01", 162, 60, "poll"),
        ("router-01", 161, 300, "poll"),
        ("router-01", 161, 60, "walk"),
    ]:
        assert calculate_offset(*changed, JitterSettings(True))[1] != original[1]


def test_effective_window_and_configured_fingerprint():
    args = ("router-01", 161, 10, "poll")
    offset, fingerprint = calculate_offset(*args, JitterSettings(True, 60))
    assert 1 <= offset <= 10
    other_offset, other_fingerprint = calculate_offset(*args, JitterSettings(True, 120))
    assert other_offset == offset
    assert other_fingerprint != fingerprint
    assert (
        calculate_offset("router-01", 161, 300, "poll", JitterSettings(True, 60))[0]
        == 56
    )


@pytest.mark.parametrize("interval,window", [(1, 60), (60, 1), (1, 1)])
def test_single_slot(interval, window):
    assert (
        calculate_offset(
            "router-01", 161, interval, "poll", JitterSettings(True, window)
        )[0]
        == 1
    )


@pytest.mark.parametrize(
    "interval,window,number,offset",
    [(300, 60, 0, 1), (300, 60, 59, 60), (10, 60, 0, 1), (10, 60, 9, 10)],
)
def test_inclusive_offset_bounds(interval, window, number, offset):
    with patch("splunk_connect_for_snmp.common.polling_jitter.hashlib.sha256") as sha:
        sha.return_value.digest.return_value = number.to_bytes(32, "big")
        assert (
            calculate_offset(
                "router-01", 161, interval, "poll", JitterSettings(True, window)
            )[0]
            == offset
        )


@pytest.mark.parametrize("microsecond,extra", [(0, 0), (1, 1), (999999, 1)])
def test_rounding_never_moves_due_earlier(microsecond, extra):
    baseline = NOW.replace(microsecond=microsecond)
    due = first_due(baseline, 20)
    assert due == NOW + timedelta(seconds=20 + extra)
    assert (
        timedelta(0) <= due - (baseline + timedelta(seconds=20)) < timedelta(seconds=1)
    )


@pytest.mark.parametrize(
    "baseline", [NOW.replace(tzinfo=None), NOW.astimezone(timezone(timedelta(hours=1)))]
)
def test_only_aware_utc_baselines(baseline):
    with pytest.raises(PollingJitterError, match="UTC"):
        first_due(baseline, 1)


def test_no_zero_or_fractional_offset():
    for offset in (0, -1, True, 0.5):
        with pytest.raises(ValueError):
            first_due(NOW, offset)


def test_positive_decimal_text():
    assert positive_integer("0060", "interval") == 60


def test_jitter_error_remains_compatible_with_value_error():
    with pytest.raises(ValueError) as error:
        calculate_offset("bad|address", 161, 60, "poll", JitterSettings(True))
    assert isinstance(error.value, PollingJitterError)


def test_shared_integer_validation_remains_generic():
    with pytest.raises(ValueError) as error:
        positive_integer(0, "Shared setting")
    assert type(error.value) is ValueError
