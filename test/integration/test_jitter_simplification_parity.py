from datetime import timedelta
from unittest.mock import patch

import pytest
from redbeat.decoder import to_timestamp
from test_automatic_jitter_policy import _entry, _load, _score
from test_automatic_jitter_policy import automatic as automatic_scheduler
from test_polling_jitter_integration import NOW

from splunk_connect_for_snmp.common import polling_jitter
from splunk_connect_for_snmp.common.polling_jitter import (
    JitterSettings,
    calculate_offset,
)

automatic = automatic_scheduler


@pytest.mark.parametrize("immediate", [False, True])
@pytest.mark.parametrize("microseconds", [0, 250000])
def test_consumed_request_has_exact_window_adoption_and_normal_recurrence(
    app, monkeypatch, automatic, immediate, microseconds
):
    entry = _entry(app, interval=600, due=NOW + timedelta(seconds=600), managed=True)
    requested_due = NOW if immediate else NOW + timedelta(seconds=15)
    entry.request_run(requested_due, run_immediately=immediate)
    accepted = app.redbeat_redis.hgetall(entry.key)
    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", JitterSettings(True, 120))
    loaded = _load(entry)
    app.now = lambda: requested_due - timedelta(microseconds=1)
    with patch.object(app, "send_task") as publish:
        automatic.maybe_due(loaded)
    publish.assert_not_called()
    assert app.redbeat_redis.hgetall(entry.key) == accepted

    reserved_at = requested_due + timedelta(microseconds=microseconds)
    app.now = lambda: reserved_at
    with patch.object(app, "send_task") as publish:
        automatic.tick()
    publish.assert_called_once()
    assert publish.call_args.args[2] == entry.kwargs
    offset, fingerprint = calculate_offset(
        "agent-01", 161, 600, "poll", JitterSettings(True, 120)
    )
    following_due = reserved_at + timedelta(seconds=600 + offset)
    stored = _load(entry)
    assert stored.total_run_count == 8
    assert stored.jitter_fingerprint == fingerprint
    assert stored.last_run_at == following_due - timedelta(seconds=600)
    assert _score(stored) == to_timestamp(following_due)
    assert not stored._strtobool(stored.run_immediately)
    assert not app.redbeat_redis.sismember("run_immediately", entry.key)

    app.now = lambda: following_due - timedelta(microseconds=1)
    with patch.object(app, "send_task") as publish:
        automatic.tick()
    publish.assert_not_called()
    app.now = lambda: following_due
    with patch.object(app, "send_task") as publish:
        automatic.tick()
    publish.assert_called_once()
    assert _load(entry).last_run_at == following_due
    assert _load(entry).total_run_count == 9
    assert _score(entry) == to_timestamp(following_due + timedelta(seconds=600))


@pytest.mark.parametrize(
    "request_seconds,microseconds,following_seconds",
    [(164, 999999, 270), (165, 0, 480), (165, 1, 480)],
)
def test_consumed_request_disable_uses_exact_fractional_boundary(
    app,
    monkeypatch,
    automatic,
    request_seconds,
    microseconds,
    following_seconds,
):
    entry = _entry(app, interval=210, due=NOW + timedelta(seconds=600), managed=True)
    requested_due = NOW + timedelta(seconds=request_seconds)
    entry.request_run(requested_due)
    accepted = app.redbeat_redis.hgetall(entry.key)
    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", JitterSettings(False, 60))
    loaded = _load(entry)
    app.now = lambda: requested_due - timedelta(microseconds=1)
    with patch.object(app, "send_task") as publish:
        automatic.maybe_due(loaded)
    publish.assert_not_called()
    assert app.redbeat_redis.hgetall(entry.key) == accepted

    app.now = lambda: requested_due + timedelta(microseconds=microseconds)
    with patch.object(app, "send_task") as publish:
        automatic.tick()
    publish.assert_called_once()
    following_due = NOW + timedelta(seconds=following_seconds)
    stored = _load(entry)
    assert stored.total_run_count == 8
    assert stored.jitter_fingerprint is None
    assert stored.last_run_at == following_due - timedelta(seconds=210)
    assert _score(stored) == following_due.timestamp()
    assert _score(stored) % 210 == 0
    assert not stored._strtobool(stored.run_immediately)
    assert not app.redbeat_redis.sismember("run_immediately", entry.key)

    app.now = lambda: following_due
    with patch.object(app, "send_task") as publish:
        automatic.tick()
    publish.assert_called_once()
    assert _load(entry).total_run_count == 9
    assert _score(entry) == (following_due + timedelta(seconds=210)).timestamp()


@pytest.mark.parametrize("immediate", [False, True])
@pytest.mark.parametrize("microseconds", [0, 250000])
def test_disable_keeps_accepted_request_after_nearest_boundary_passes(
    app, monkeypatch, automatic, immediate, microseconds
):
    requested_due = NOW + timedelta(seconds=80)
    entry = _entry(app, interval=60, due=requested_due, managed=True)
    if immediate:
        app.now = lambda: requested_due
    entry.request_run(requested_due, run_immediately=immediate)
    accepted = app.redbeat_redis.hgetall(entry.key)
    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", JitterSettings(False, 60))
    if not immediate:
        app.now = lambda: NOW + timedelta(seconds=70)
        with patch.object(app, "send_task") as publish:
            automatic.tick()
        publish.assert_not_called()
    loaded = _load(entry)
    app.now = lambda: requested_due - timedelta(microseconds=1)
    with patch.object(app, "send_task") as publish:
        automatic.maybe_due(loaded)
    publish.assert_not_called()
    assert app.redbeat_redis.hgetall(entry.key) == accepted
    assert _score(entry) == requested_due.timestamp()

    app.now = lambda: requested_due + timedelta(microseconds=microseconds)
    with patch.object(app, "send_task") as publish:
        automatic.tick()
    publish.assert_called_once()
    following_due = NOW + timedelta(seconds=120)
    stored = _load(entry)
    assert stored.total_run_count == 8
    assert stored.last_run_at == NOW + timedelta(seconds=60)
    assert stored.jitter_fingerprint is None
    assert not stored._strtobool(stored.run_immediately)
    assert _score(stored) == following_due.timestamp()
    assert not app.redbeat_redis.sismember("run_immediately", entry.key)
