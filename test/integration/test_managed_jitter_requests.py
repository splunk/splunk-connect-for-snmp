import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from celery.schedules import schedule
from redbeat.decoder import to_timestamp
from redbeat.schedulers import RedBeatScheduler, RedBeatSchedulerEntry
from test_polling_jitter_integration import NOW, create_entry

from splunk_connect_for_snmp.common import polling_jitter
from splunk_connect_for_snmp.common.polling_jitter import (
    JitterSettings,
    calculate_offset,
    first_due,
)


def saved(entry):
    return RedBeatSchedulerEntry.from_key(entry.key, app=entry.app)


def reserve_initial(app, entry):
    due = app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key)
    app.now = lambda: datetime.fromtimestamp(due, timezone.utc)
    next(saved(entry))
    return saved(entry)


@pytest.mark.parametrize("already_reserved", [False, True])
def test_initial_creator_finds_the_other_creators_walk(
    app, monkeypatch, already_reserved
):
    manager, data, entry = create_entry(app, monkeypatch, "walk", 1800)
    if already_reserved:
        entry = reserve_initial(app, entry)
    due = entry.last_run_at + entry.schedule.run_every
    context = dict(entry.first_run_kwargs)
    count = entry.total_run_count
    request_time = app.now() + timedelta(seconds=1)
    app.now = lambda: request_time
    data["kwargs"]["profile"] = "UpdatedWalk"

    manager.manage_task(initial_registration=True, **data)

    current = saved(entry)
    assert current.entry_id == entry.entry_id
    assert current.total_run_count == count
    assert current.kwargs["profile"] == "UpdatedWalk"
    if already_reserved:
        assert current.is_due()[0]
        assert current.first_run_kwargs == {}
    else:
        assert current.last_run_at + current.schedule.run_every == due
        assert current.first_run_kwargs == context
        assert not current.is_due()[0]


@pytest.mark.parametrize("shift", [-10, 10])
def test_inventory_request_replaces_ordinary_due_and_respects_not_before(
    app, monkeypatch, shift
):
    manager, data, entry = create_entry(app, monkeypatch, "walk", 1800)
    entry = reserve_initial(app, entry)
    old_due = app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key)
    count = entry.total_run_count
    offset, fingerprint = calculate_offset(
        "router-01", 161, 1800, "walk", JitterSettings(True, 60)
    )
    request_time = datetime.fromtimestamp(old_due, timezone.utc) + timedelta(
        seconds=shift - offset
    )
    app.now = lambda: request_time
    data["kwargs"]["profile"] = "UpdatedWalk"
    manager.manage_task(inventory_update=True, **data)

    entry = saved(entry)
    due = first_due(request_time, offset)
    assert entry._strtobool(entry.run_immediately)
    assert entry.jitter_fingerprint == fingerprint
    assert entry.first_run_kwargs == {}
    assert entry.last_run_at == due - entry.schedule.run_every
    assert entry.total_run_count == count
    assert (
        app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key)
        == due.timestamp()
    )
    assert not app.redbeat_redis.sismember("run_immediately", entry.key)

    scheduler = RedBeatScheduler(app, lazy=True, max_interval=3600)
    try:
        app.now = lambda: due - timedelta(microseconds=1)
        with patch.object(app, "send_task") as publish:
            scheduler.tick()
        publish.assert_not_called()
        assert not saved(entry).is_due()[0]
        app.now = lambda: due
        with patch.object(app, "send_task") as publish:
            scheduler.tick()
        publish.assert_called_once()
        assert publish.call_args.args[2]["profile"] == "UpdatedWalk"
        assert "_schedule_context" not in publish.call_args.args[2]
    finally:
        scheduler.close()

    entry = saved(entry)
    assert not entry._strtobool(entry.run_immediately)
    assert entry.total_run_count == 2
    assert entry.last_run_at == due
    assert (
        app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key)
        == (due + timedelta(seconds=1800)).timestamp()
    )


@pytest.mark.parametrize("window", [1, 10])
def test_inventory_refresh_uses_applied_window_and_preserves_microseconds(
    app, monkeypatch, window
):
    manager, data, entry = create_entry(app, monkeypatch, "walk", 1800, window=window)
    entry = reserve_initial(app, entry)
    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", JitterSettings(True, 60))
    request_time = NOW + timedelta(minutes=2, microseconds=250000)
    app.now = lambda: request_time
    offset, fingerprint = calculate_offset(
        "router-01", 161, 1800, "walk", JitterSettings(True, window)
    )
    manager.manage_task(inventory_update=True, **data)

    entry = saved(entry)
    assert entry.jitter_fingerprint == fingerprint
    due = request_time + timedelta(seconds=offset)
    assert entry.last_run_at + entry.schedule.run_every == due
    assert entry.last_run_at.microsecond == request_time.microsecond
    assert app.redbeat_redis.zscore(
        app.redbeat_conf.schedule_key, entry.key
    ) == to_timestamp(due)
    assert entry.first_run_kwargs == {}


def test_repeated_inventory_edits_keep_earliest_due_and_latest_payload(
    app, monkeypatch
):
    manager, data, entry = create_entry(app, monkeypatch, "walk", 1800)
    count = entry.total_run_count
    app.now = lambda: NOW + timedelta(minutes=2)
    data["kwargs"]["profile"] = "FirstEdit"
    manager.manage_task(inventory_update=True, **data)
    first = saved(entry)
    due = first.last_run_at + first.schedule.run_every

    app.now = lambda: NOW + timedelta(minutes=2, seconds=5)
    data["kwargs"]["profile"] = "LatestEdit"
    manager.manage_task(inventory_update=True, **data)
    second = saved(entry)
    assert second.last_run_at + second.schedule.run_every == due
    assert second.kwargs["profile"] == "LatestEdit"
    assert second.total_run_count == count

    manager.manage_task(inventory_update=True, **data)
    third = saved(entry)
    assert third.last_run_at + third.schedule.run_every == due
    assert third.total_run_count == count
    assert third.kwargs == second.kwargs


@pytest.mark.parametrize("urgent_first", [False, True])
def test_urgent_requests_win_in_both_arrival_orders(app, monkeypatch, urgent_first):
    manager, data, entry = create_entry(app, monkeypatch, "walk", 1800)
    entry = reserve_initial(app, entry)
    options = entry.options
    request_time = NOW + timedelta(minutes=2)
    app.now = lambda: request_time
    if urgent_first:
        manager.manage_task(name=data["name"], run_immediately=True)
    else:
        manager.manage_task(inventory_update=True, **data)

    app.now = lambda: request_time + timedelta(seconds=1)
    if urgent_first:
        data["kwargs"]["profile"] = "LatestEdit"
        manager.manage_task(inventory_update=True, **data)
    else:
        manager.manage_task(name=data["name"], run_immediately=True)
    entry = saved(entry)
    assert entry._strtobool(entry.run_immediately)
    expected = request_time if urgent_first else request_time + timedelta(seconds=1)
    assert entry.last_run_at + entry.schedule.run_every == expected
    assert entry.is_due()[0]
    assert app.redbeat_redis.sismember("run_immediately", entry.key)
    assert entry.first_run_kwargs == {}
    if urgent_first:
        assert entry.kwargs["profile"] == "LatestEdit"
    assert entry.options == options


def test_disabled_settings_keep_accepted_request_until_an_immediate_inventory_update(
    app, monkeypatch
):
    manager, data, entry = create_entry(app, monkeypatch, "walk", 1800)
    entry = reserve_initial(app, entry)
    request_time = NOW + timedelta(minutes=2)
    app.now = lambda: request_time
    manager.manage_task(inventory_update=True, **data)
    accepted = app.redbeat_redis.hgetall(entry.key)
    due = app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key)
    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", JitterSettings(False, 60))
    assert app.redbeat_redis.hgetall(entry.key) == accepted
    assert app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key) == due
    assert not saved(entry).is_due()[0]

    app.now = lambda: request_time + timedelta(seconds=1)
    data["kwargs"]["profile"] = "DisabledEdit"
    manager.manage_task(inventory_update=True, **data)
    entry = saved(entry)
    assert entry._strtobool(entry.run_immediately)
    assert entry.last_run_at + entry.schedule.run_every == app.now()
    assert entry.kwargs["profile"] == "DisabledEdit"
    assert entry.is_due()[0]
    assert entry.jitter_fingerprint


def test_inventory_interval_edit_keeps_key_and_applied_window(app, monkeypatch):
    manager, data, entry = create_entry(app, monkeypatch, "walk", 1800, window=10)
    entry = reserve_initial(app, entry)
    count = entry.total_run_count
    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", JitterSettings(True, 60))
    data["schedule"] = schedule(1200)
    request_time = NOW + timedelta(minutes=2)
    app.now = lambda: request_time
    offset, fingerprint = calculate_offset(
        "router-01", 161, 1200, "walk", JitterSettings(True, 10)
    )
    manager.manage_task(inventory_update=True, **data)
    updated = saved(entry)
    assert updated.key == entry.key
    assert updated.schedule.run_every == timedelta(seconds=1200)
    assert updated.jitter_fingerprint == fingerprint
    assert updated.last_run_at + updated.schedule.run_every == first_due(
        request_time, offset
    )
    assert updated.total_run_count == count
    app.now = lambda: first_due(request_time, offset)
    next(updated)
    assert (
        app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key)
        == (app.now() + timedelta(seconds=1200)).timestamp()
    )


@pytest.mark.parametrize("interval", [60, 300])
def test_short_poll_definition_update_preserves_accepted_urgent_request(
    app, monkeypatch, interval
):
    manager, data, entry = create_entry(app, monkeypatch, interval=interval)
    options = entry.options
    manager.manage_task(name=data["name"], run_immediately=True)
    request = saved(entry)
    metadata = app.redbeat_redis.hget(entry.key, "meta")
    due = app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key)
    data["kwargs"]["profiles"] = ["UpdatedA", "UpdatedB"]
    manager.manage_task(**data)

    entry = saved(entry)
    assert entry.kwargs["profiles"] == ["UpdatedA", "UpdatedB"]
    assert entry.run_immediately == request.run_immediately
    assert entry.options == options
    assert app.redbeat_redis.hget(entry.key, "meta") == metadata
    assert app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key) == due
    assert app.redbeat_redis.sismember("run_immediately", entry.key)


@pytest.mark.parametrize("interval", [301, 600])
def test_existing_long_poll_refresh_overrides_its_initial_phase(
    app, monkeypatch, interval
):
    manager, data, entry = create_entry(app, monkeypatch, interval=interval)
    assert not entry.is_due()[0]
    manager.manage_task(initial_registration=True, **data)
    entry = saved(entry)
    assert entry._strtobool(entry.run_immediately)
    assert entry.last_run_at + entry.schedule.run_every == NOW
    assert entry.is_due()[0]
    assert (
        app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key)
        == NOW.timestamp()
    )
    invocation = next(entry)
    assert "_schedule_context" not in invocation.kwargs
    assert not saved(entry)._strtobool(saved(entry).run_immediately)


def test_restart_request_preserves_run_count(app, monkeypatch):
    manager, data, entry = create_entry(app, monkeypatch, "walk", 1800)
    entry = reserve_initial(app, entry)
    app.now = lambda: NOW + timedelta(minutes=5)
    manager.manage_task(name=data["name"], run_immediately=True)
    entry = saved(entry)
    assert entry._strtobool(entry.run_immediately)
    assert entry.last_run_at + entry.schedule.run_every == app.now()
    assert entry.is_due()[0]
    assert entry.total_run_count == 1
    next(entry)
    updated = saved(entry)
    assert updated.total_run_count == 2
    assert (
        app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key)
        == (app.now() + timedelta(seconds=1800)).timestamp()
    )


def test_enabled_legacy_inventory_update_is_immediate_without_adoption(
    app, monkeypatch
):
    from splunk_connect_for_snmp import customtaskmanager
    from splunk_connect_for_snmp.common.task_generator import WalkTaskGenerator

    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", JitterSettings(True, 60))
    monkeypatch.setattr(customtaskmanager, "app", app)
    app.now = lambda: NOW
    data = WalkTaskGenerator(
        "router-legacy:161", 1800, app, None, "Walk"
    ).generate_task_definition()
    manager = customtaskmanager.CustomPeriodicTaskManager()
    manager.manage_task(**data)
    manager.manage_task(inventory_update=True, **data)
    key = "redbeat:" + data["name"]
    entry = RedBeatSchedulerEntry.from_key(key, app=app)
    assert entry.is_due()[0]
    assert not app.redbeat_redis.hexists(key, "jitter_fingerprint")
    assert entry.first_run_kwargs == {}


def test_partial_restart_request_keeps_latest_options_and_arguments(app, monkeypatch):
    manager, data, entry = create_entry(app, monkeypatch, "walk", 1800)
    options = entry.options
    data["kwargs"]["profile"] = "LatestWalk"
    data["run_immediately"] = False
    manager.manage_task(**data)
    manager.manage_task(name=data["name"], run_immediately=True)
    entry = saved(entry)
    assert entry.kwargs == data["kwargs"]
    assert entry.args == data["args"]
    assert entry.options == options
    assert entry.first_run_kwargs == {}
    assert entry._strtobool(entry.run_immediately)


def test_definition_only_walk_update_preserves_delayed_request(app, monkeypatch):
    manager, data, entry = create_entry(app, monkeypatch, "walk", 1800)
    manager.manage_task(inventory_update=True, **data)
    before = saved(entry)
    metadata = app.redbeat_redis.hget(entry.key, "meta")
    due = app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key)
    data["run_immediately"] = False
    data["kwargs"]["profile"] = "PayloadOnly"
    manager.manage_task(**data)
    after = saved(entry)
    assert after.kwargs["profile"] == "PayloadOnly"
    assert after.run_immediately == before.run_immediately
    assert after.jitter_fingerprint == before.jitter_fingerprint
    assert app.redbeat_redis.hget(entry.key, "meta") == metadata
    assert app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key) == due
    assert not app.redbeat_redis.sismember("run_immediately", entry.key)
    assert (
        json.loads(app.redbeat_redis.hget(entry.key, "definition"))["run_immediately"]
        == "True"
    )


@pytest.mark.parametrize("changed", [False, True])
def test_inventory_record_manager_requests_only_actual_changes(
    app, monkeypatch, changed
):
    from splunk_connect_for_snmp.common import inventory_processor

    manager, _, entry = create_entry(app, monkeypatch, "walk", 1800)
    entry = reserve_initial(app, entry)
    monkeypatch.setattr(inventory_processor, "app", app)
    request_time = NOW + timedelta(minutes=2)
    app.now = lambda: request_time
    before = app.redbeat_redis.hgetall(entry.key)
    mongo = MagicMock()
    mongo.sc4snmp.inventory.find_one.return_value = {"_id": "existing-record"}
    mongo.sc4snmp.inventory.update_one.return_value = SimpleNamespace(
        matched_count=1, modified_count=int(changed), upserted_id=None
    )
    record = SimpleNamespace(
        address="router-01", port=161, walk_interval=1800, asdict=lambda: {}
    )
    inventory_processor.InventoryRecordManager(mongo, manager).update(
        record, {"profiles": "A", "walk_interval": "1800"}, {}, False
    )
    if not changed:
        assert app.redbeat_redis.hgetall(entry.key) == before
        return
    offset, fingerprint = calculate_offset(
        "router-01", 161, 1800, "walk", JitterSettings(True, 60)
    )
    entry = saved(entry)
    assert entry._strtobool(entry.run_immediately)
    assert entry.last_run_at + entry.schedule.run_every == first_due(
        request_time, offset
    )
    assert entry.jitter_fingerprint == fingerprint
