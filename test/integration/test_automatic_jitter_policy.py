import json
import runpy
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from redbeat.decoder import RedBeatJSONEncoder
from redbeat.schedulers import RedBeatScheduler, RedBeatSchedulerEntry
from test_polling_jitter_integration import NOW

from splunk_connect_for_snmp.common import polling_jitter
from splunk_connect_for_snmp.common.polling_jitter import (
    JitterSettings,
    calculate_offset,
)
from splunk_connect_for_snmp.common.task_generator import (
    PollTaskGenerator,
    WalkTaskGenerator,
)
from splunk_connect_for_snmp.jitter_reconcile import apply_entry_policy


def _load(entry):
    return RedBeatSchedulerEntry.from_key(entry.key, app=entry.app)


def _score(entry):
    return entry.app.redbeat_redis.zscore(
        entry.app.redbeat_conf.schedule_key, entry.key
    )


def _entry(
    app,
    device="agent-01",
    kind="poll",
    interval=60,
    due=NOW,
    count=7,
    managed=False,
    window=60,
    immediate=False,
):
    generator = (
        WalkTaskGenerator(f"{device}:161", interval, app, None, "Walk")
        if kind == "walk"
        else PollTaskGenerator(f"{device}:161", interval, app, None, ["A", "B"], 120)
    )
    definition = generator.generate_task_definition()
    definition["run_immediately"] = immediate
    entry = RedBeatSchedulerEntry(**definition)
    entry.total_run_count = count
    entry.last_run_at = due - timedelta(seconds=interval)
    if managed:
        _, fingerprint = calculate_offset(
            device, 161, interval, kind, JitterSettings(True, window)
        )
        entry.save_with_first_due(due, fingerprint)
    else:
        entry.save()
        meta = {
            "last_run_at": entry.last_run_at,
            "total_run_count": count,
        }
        app.redbeat_redis.hset(
            entry.key, "meta", json.dumps(meta, cls=RedBeatJSONEncoder)
        )
        app.redbeat_redis.zadd(
            app.redbeat_conf.schedule_key, {entry.key: due.timestamp()}
        )
    return _load(entry)


@pytest.fixture
def automatic(app, monkeypatch):
    app.now = lambda: NOW
    app.conf.redbeat_entry_policy = apply_entry_policy
    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", JitterSettings(True, 60))
    scheduler = RedBeatScheduler(app, lazy=True, max_interval=10)
    try:
        yield scheduler
    finally:
        scheduler.close()


def test_500_devices_adopt_change_window_disable_and_reenable(
    app, monkeypatch, automatic
):
    entries = [
        _entry(app, f"agent-{index:04}", kind, interval)
        for index in range(500)
        for kind, interval in (("walk", 1800), ("poll", 60), ("poll", 600))
    ]
    payloads = {entry.key: (entry.kwargs, entry.options) for entry in entries}
    keys = {entry.key for entry in entries}
    assert len(keys) == 1500
    settings_sequence = (
        JitterSettings(True, 60),
        JitterSettings(True, 120),
        JitterSettings(False, 120),
        JitterSettings(True, 120),
    )
    for transition, settings in enumerate(settings_sequence):
        monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", settings)
        with patch.object(app, "send_task") as publish:
            for original in entries:
                entry = _load(original)
                seconds = int(entry.schedule.run_every.total_seconds())
                kind = "walk" if entry.task.endswith(".walk") else "poll"
                device = entry.kwargs["address"].rsplit(":", 1)[0]
                due = datetime.fromtimestamp(_score(entry), timezone.utc)
                before = app.redbeat_redis.hgetall(entry.key)
                app.now = lambda: due - timedelta(microseconds=1)
                with patch.object(polling_jitter.hashlib, "sha256") as hashing:
                    automatic.maybe_due(entry)
                hashing.assert_not_called()
                assert app.redbeat_redis.hgetall(entry.key) == before
                assert _score(entry) == due.timestamp()

                app.now = lambda: due
                automatic.maybe_due(_load(entry))
                stored = _load(entry)
                baseline = due.timestamp() + seconds
                if settings.enabled:
                    offset, fingerprint = calculate_offset(
                        device, 161, seconds, kind, settings
                    )
                    same_cap = transition == 1 and seconds == 60
                    expected = baseline + (0 if same_cap else offset)
                    assert stored.jitter_fingerprint == fingerprint
                else:
                    quotient, remainder = divmod(baseline, seconds)
                    expected = (quotient + (remainder * 2 >= seconds)) * seconds
                    assert stored.jitter_fingerprint is None
                assert _score(stored) == expected
                assert expected > due.timestamp()
                assert stored.total_run_count == 8 + transition
                assert (stored.kwargs, stored.options) == payloads[stored.key]
        assert publish.call_count == 1500

    restarted = RedBeatScheduler(app, lazy=True, max_interval=10)
    try:
        app.now = lambda: NOW - timedelta(seconds=1)
        before = {
            entry.key: (app.redbeat_redis.hgetall(entry.key), _score(entry))
            for entry in entries
        }
        with patch.object(polling_jitter.hashlib, "sha256") as hashing:
            for entry in entries:
                restarted.maybe_due(_load(entry))
        hashing.assert_not_called()
        assert before == {
            entry.key: (app.redbeat_redis.hgetall(entry.key), _score(entry))
            for entry in entries
        }
        assert app.redbeat_redis.zcard(app.redbeat_conf.schedule_key) == 1500
        assert (
            set(app.redbeat_redis.zrange(app.redbeat_conf.schedule_key, 0, -1)) == keys
        )
    finally:
        restarted.close()


@pytest.mark.parametrize("kind,interval", [("walk", 1800), ("poll", 60), ("poll", 600)])
def test_disabled_invalid_window_preserves_saved_run_and_allows_reenable(
    app, monkeypatch, automatic, kind, interval
):
    due = NOW + timedelta(seconds=20)
    entry = _entry(app, kind=kind, interval=interval, due=due, managed=True, window=120)
    accepted = app.redbeat_redis.hgetall(entry.key)
    monkeypatch.setenv("POLLING_JITTER_ENABLED", "false")
    monkeypatch.setenv("POLLING_JITTER_WINDOW_SECONDS", "abc")
    settings = runpy.run_path(polling_jitter.__file__)["JITTER_SETTINGS"]
    assert (settings.enabled, settings.window_seconds) == (False, 60)
    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", settings)

    app.now = lambda: due - timedelta(microseconds=1)
    with patch.object(app, "send_task") as publish:
        automatic.maybe_due(_load(entry))
    publish.assert_not_called()
    assert app.redbeat_redis.hgetall(entry.key) == accepted
    assert _score(entry) == due.timestamp()

    app.now = lambda: due
    with patch.object(app, "send_task") as publish:
        automatic.maybe_due(_load(entry))
    publish.assert_called_once()
    stored = _load(entry)
    baseline = due.timestamp() + interval
    quotient, remainder = divmod(baseline, interval)
    following = (quotient + (remainder * 2 >= interval)) * interval
    assert _score(stored) == following
    assert stored.jitter_fingerprint is None
    assert stored.total_run_count == 8
    assert stored.kwargs == entry.kwargs
    assert not app.redbeat_redis.sismember("run_immediately", entry.key)

    app.now = lambda: datetime.fromtimestamp(following, timezone.utc)
    with patch.object(app, "send_task") as publish:
        automatic.maybe_due(stored)
    publish.assert_called_once()
    assert _score(entry) == following + interval
    assert _load(entry).jitter_fingerprint is None

    monkeypatch.setenv("POLLING_JITTER_ENABLED", "true")
    monkeypatch.setenv("POLLING_JITTER_WINDOW_SECONDS", "120")
    settings = runpy.run_path(polling_jitter.__file__)["JITTER_SETTINGS"]
    assert (settings.enabled, settings.window_seconds) == (True, 120)
    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", settings)
    stored_due = _score(entry)
    app.now = lambda: datetime.fromtimestamp(stored_due, timezone.utc)
    with patch.object(app, "send_task") as publish:
        automatic.maybe_due(_load(entry))
    publish.assert_called_once()
    offset, fingerprint = calculate_offset("agent-01", 161, interval, kind, settings)
    assert _score(entry) == stored_due + interval + offset
    assert _load(entry).jitter_fingerprint == fingerprint
    assert _load(entry).total_run_count == 10


@pytest.mark.parametrize("kind,interval", [("walk", 1800), ("poll", 60), ("poll", 600)])
def test_recovery_first_run_keeps_old_due_then_phases_following_interval(
    app, monkeypatch, automatic, kind, interval
):
    immediate = kind == "walk" or interval > 300
    first = NOW if immediate else NOW + timedelta(seconds=interval)
    entry = _entry(
        app, kind=kind, interval=interval, due=first, count=0, immediate=immediate
    )
    before = app.redbeat_redis.hgetall(entry.key)
    if not immediate:
        app.now = lambda: first - timedelta(microseconds=1)
        with patch.object(app, "send_task") as publish:
            automatic.maybe_due(entry)
        publish.assert_not_called()
    assert app.redbeat_redis.hgetall(entry.key) == before
    assert not _load(entry).jitter_fingerprint
    app.now = lambda: first
    with patch.object(app, "send_task") as publish:
        automatic.tick()
    publish.assert_called_once()
    stored = _load(entry)
    offset, fingerprint = calculate_offset(
        "agent-01", 161, interval, kind, JitterSettings(True, 60)
    )
    assert stored.total_run_count == 1
    assert stored.jitter_fingerprint == fingerprint
    assert _score(stored) == (first + timedelta(seconds=interval + offset)).timestamp()
    assert "_schedule_context" not in publish.call_args.args[2]


@pytest.mark.parametrize("kind,interval", [("walk", 1800), ("poll", 60), ("poll", 600)])
def test_exact_adoption_due_and_normal_following_intervals(
    app, monkeypatch, automatic, kind, interval
):
    entry = _entry(app, kind=kind, interval=interval)
    with patch.object(app, "send_task") as publish:
        automatic.tick()
    publish.assert_called_once()
    offset, _ = calculate_offset(
        "agent-01", 161, interval, kind, JitterSettings(True, 60)
    )
    due = datetime.fromtimestamp(_score(entry), timezone.utc)
    assert due == NOW + timedelta(seconds=interval + offset)
    for cycle in range(3):
        current = due + timedelta(seconds=cycle * interval)
        app.now = lambda: current - timedelta(microseconds=1)
        with patch.object(app, "send_task") as publish:
            automatic.tick()
        publish.assert_not_called()
        app.now = lambda: current
        with patch.object(app, "send_task") as publish:
            automatic.tick()
        publish.assert_called_once()
        stored = _load(entry)
        assert stored.total_run_count == 9 + cycle
        assert stored.last_run_at == current
        assert _score(stored) == (current + timedelta(seconds=interval)).timestamp()


def test_same_effective_window_changes_only_saved_fingerprint(
    app, monkeypatch, automatic
):
    entry = _entry(app, due=NOW + timedelta(seconds=41), managed=True)
    before = app.redbeat_redis.hgetall(entry.key)
    score = _score(entry)
    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", JitterSettings(True, 120))
    automatic.maybe_due(entry)
    assert app.redbeat_redis.hgetall(entry.key) == before
    assert _score(entry) == score
    app.now = lambda: datetime.fromtimestamp(score, timezone.utc)
    with patch.object(app, "send_task") as publish:
        automatic.maybe_due(_load(entry))
    publish.assert_called_once()
    after = app.redbeat_redis.hgetall(entry.key)
    assert set(before) == set(after)
    assert {field for field in before if before[field] != after[field]} == {
        "jitter_fingerprint",
        "meta",
    }
    assert _score(entry) == score + 60


@pytest.mark.parametrize("old_window,new_window", [(120, 10), (60, 120)])
def test_effective_window_change_adds_new_offset_once_without_subtracting_old(
    app, monkeypatch, automatic, old_window, new_window
):
    entry = _entry(
        app,
        interval=600,
        due=NOW + timedelta(seconds=55),
        managed=True,
        window=old_window,
    )
    offset, fingerprint = calculate_offset(
        "agent-01", 161, 600, "poll", JitterSettings(True, new_window)
    )
    monkeypatch.setattr(
        polling_jitter, "JITTER_SETTINGS", JitterSettings(True, new_window)
    )
    before = app.redbeat_redis.hgetall(entry.key)
    automatic.maybe_due(entry)
    assert app.redbeat_redis.hgetall(entry.key) == before
    assert _score(entry) == (NOW + timedelta(seconds=55)).timestamp()
    app.now = lambda: NOW + timedelta(seconds=55)
    with patch.object(app, "send_task") as publish:
        automatic.maybe_due(_load(entry))
    publish.assert_called_once()
    stored = _load(entry)
    assert stored.jitter_fingerprint == fingerprint
    assert _score(stored) == (NOW + timedelta(seconds=655 + offset)).timestamp()
    before = app.redbeat_redis.hgetall(entry.key)
    with patch.object(polling_jitter.hashlib, "sha256") as hashing:
        automatic.maybe_due(stored)
    hashing.assert_not_called()
    assert app.redbeat_redis.hgetall(entry.key) == before


@pytest.mark.parametrize("due_seconds,expected", [(80, 120), (90, 180), (100, 180)])
def test_disable_selects_nearest_future_boundary_with_ties_later(
    app, monkeypatch, automatic, due_seconds, expected
):
    entry = _entry(app, due=NOW + timedelta(seconds=due_seconds), managed=True)
    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", JitterSettings(False, 60))
    before = app.redbeat_redis.hgetall(entry.key)
    automatic.maybe_due(entry)
    assert app.redbeat_redis.hgetall(entry.key) == before
    assert _score(entry) == (NOW + timedelta(seconds=due_seconds)).timestamp()
    app.now = lambda: NOW + timedelta(seconds=due_seconds)
    with patch.object(app, "send_task") as publish:
        automatic.maybe_due(_load(entry))
    publish.assert_called_once()
    stored = _load(entry)
    assert stored.jitter_fingerprint is None
    assert _score(stored) == (NOW + timedelta(seconds=expected)).timestamp()
    assert stored.last_run_at == NOW + timedelta(seconds=expected - 60)
    assert stored.total_run_count == 8


@pytest.mark.parametrize(
    "after_lower,microseconds,expected",
    [(104, 500000, 270), (105, 0, 480), (105, 1, 480), (106, 500000, 480)],
)
def test_disable_210_second_grid_uses_fractional_reservation_without_rounding(
    app, monkeypatch, automatic, after_lower, microseconds, expected
):
    # These 210-second UTC boundaries are 12:04:30 and 12:08:00 on this date.
    # Disable chooses the one nearest to reservation + interval, with ties later.
    due = NOW + timedelta(seconds=60 + after_lower)
    entry = _entry(app, interval=210, due=due, managed=True)
    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", JitterSettings(False, 60))
    app.now = lambda: due + timedelta(microseconds=microseconds)
    with patch.object(app, "send_task") as publish:
        automatic.maybe_due(_load(entry))
    publish.assert_called_once()
    stored = _load(entry)
    assert stored.jitter_fingerprint is None
    assert stored.total_run_count == 8
    assert _score(stored) == (NOW + timedelta(seconds=expected)).timestamp()
    assert _score(stored) % 210 == 0


def test_disable_keeps_current_run_when_nearest_boundary_has_passed(
    app, monkeypatch, automatic
):
    entry = _entry(app, due=NOW + timedelta(seconds=80), managed=True)
    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", JitterSettings(False, 60))
    app.now = lambda: NOW + timedelta(seconds=70)
    with patch.object(app, "send_task") as publish:
        automatic.tick()
    publish.assert_not_called()
    assert _score(entry) == (NOW + timedelta(seconds=80)).timestamp()
    assert _load(entry).jitter_fingerprint
    app.now = lambda: NOW + timedelta(seconds=80)
    with patch.object(app, "send_task") as publish:
        automatic.tick()
    publish.assert_called_once()
    stored = _load(entry)
    assert stored.jitter_fingerprint is None
    assert stored.total_run_count == 8
    assert _score(stored) == (NOW + timedelta(seconds=120)).timestamp()


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("run_immediately", [False, True])
def test_pending_requests_run_before_policy_changes(
    app, monkeypatch, automatic, enabled, run_immediately
):
    entry = _entry(app, interval=600, due=NOW + timedelta(seconds=600), managed=True)
    request_due = NOW if run_immediately else NOW + timedelta(seconds=15)
    entry.request_run(request_due, run_immediately=run_immediately)
    accepted = app.redbeat_redis.hgetall(entry.key)
    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", JitterSettings(enabled, 120))
    loaded = _load(entry)
    app.now = lambda: request_due - timedelta(microseconds=1)
    with patch.object(app, "send_task") as publish:
        automatic.maybe_due(loaded)
    publish.assert_not_called()
    assert app.redbeat_redis.hgetall(entry.key) == accepted
    app.now = lambda: request_due
    with patch.object(app, "send_task") as publish:
        automatic.tick()
    publish.assert_called_once()
    stored = _load(entry)
    assert not stored._strtobool(stored.run_immediately)
    assert stored.total_run_count == 8
    assert bool(stored.jitter_fingerprint) is enabled


def test_initial_walk_arguments_are_served_before_window_adoption(
    app, monkeypatch, automatic
):
    entry = _entry(app, kind="walk", interval=1800, count=0, managed=True)
    definition = json.loads(app.redbeat_redis.hget(entry.key, "definition"))
    definition["first_run_kwargs"] = {"_schedule_context": "initial_registration"}
    app.redbeat_redis.hset(entry.key, "definition", json.dumps(definition))
    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", JitterSettings(True, 120))
    with patch.object(app, "send_task") as publish:
        automatic.tick()
    publish.assert_called_once()
    assert publish.call_args.args[2]["_schedule_context"] == "initial_registration"
    stored = _load(entry)
    assert stored.total_run_count == 1
    assert stored.first_run_kwargs == {}
    assert stored.jitter_fingerprint.startswith("sha256-v1:120:")


@pytest.mark.parametrize("excluded", ["disabled", "discovery"])
def test_disabled_and_nonpolling_entries_keep_their_existing_state(
    app, monkeypatch, automatic, excluded
):
    entry = _entry(app, due=NOW + timedelta(seconds=60))
    definition = json.loads(app.redbeat_redis.hget(entry.key, "definition"))
    if excluded == "disabled":
        definition["enabled"] = "False"
    else:
        definition["task"] = "splunk_connect_for_snmp.discovery.tasks.discovery"
    app.redbeat_redis.hset(entry.key, "definition", json.dumps(definition))
    before = app.redbeat_redis.hgetall(entry.key)
    loaded = _load(entry)
    assert apply_entry_policy(loaded) is None
    assert app.redbeat_redis.hgetall(entry.key) == before
    assert _score(entry) == (NOW + timedelta(seconds=60)).timestamp()


def test_one_bad_saved_policy_does_not_block_other_due_entries(
    app, monkeypatch, automatic
):
    invalid = _entry(app, "agent-invalid", managed=True)
    valid = _entry(app, "agent-valid")
    app.redbeat_redis.hset(invalid.key, "jitter_fingerprint", json.dumps("invalid"))
    with patch.object(app, "send_task") as publish:
        automatic.tick()
    assert publish.call_count == 2
    assert _load(valid).jitter_fingerprint.startswith("sha256-v1:60:")
    assert _score(valid) > NOW.timestamp()
    assert _score(invalid) == (NOW + timedelta(seconds=60)).timestamp()
    assert _load(invalid).total_run_count == 8


@pytest.mark.parametrize("window,interval", [(1, 60), (10, 10), (60, 10)])
def test_positive_offset_bounds_and_profiles_remain_grouped(
    app, monkeypatch, automatic, window, interval
):
    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", JitterSettings(True, window))
    entry = _entry(app, interval=interval)
    options = entry.options
    automatic.maybe_due(entry)
    stored = _load(entry)
    offset = _score(stored) - (NOW + timedelta(seconds=interval)).timestamp()
    assert 1 <= offset <= min(window, interval)
    if window == 1:
        assert offset == 1
    assert stored.kwargs["profiles"] == ["A", "B"]
    assert stored.options == options
    assert app.redbeat_redis.zcard(app.redbeat_conf.schedule_key) == 1


def test_restart_continues_mixed_policies_without_rephasing_completed_entries(
    app, monkeypatch, automatic
):
    applied = _entry(
        app, "agent-applied", due=NOW + timedelta(seconds=60), managed=True
    )
    waiting = _entry(app, "agent-waiting")
    before = app.redbeat_redis.hgetall(applied.key)
    restarted = RedBeatScheduler(app, lazy=True, max_interval=10)
    try:
        with patch.object(app, "send_task") as publish:
            restarted.tick()
        publish.assert_called_once()
        assert _load(waiting).jitter_fingerprint
        assert app.redbeat_redis.hgetall(applied.key) == before
    finally:
        restarted.close()
