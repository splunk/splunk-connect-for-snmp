"""SC4SNMP scheduling policy checks against disposable Redis and real RedBeat."""

import json
import logging
from datetime import datetime, timedelta, timezone
from queue import Empty
from unittest.mock import patch

import pytest
from redbeat.decoder import to_timestamp
from redbeat.schedulers import RedBeatScheduler, RedBeatSchedulerEntry

from splunk_connect_for_snmp.common import polling_jitter
from splunk_connect_for_snmp.common.polling_jitter import JitterSettings

NOW = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)


def read_message(queue):
    try:
        return queue.get(block=False)
    except Empty:
        return None


def create_entry(app, monkeypatch, kind="poll", interval=60, window=60):
    """
    Create a new device schedule through SC4SNMP's actual task manager.

    :return: Manager, generated task definition and saved RedBeat entry
    """
    from splunk_connect_for_snmp import customtaskmanager
    from splunk_connect_for_snmp.common.task_generator import (
        PollTaskGenerator,
        WalkTaskGenerator,
    )

    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", JitterSettings(True, window))
    monkeypatch.setattr(customtaskmanager, "app", app)
    app.now = lambda: NOW
    generator = (
        WalkTaskGenerator("router-01:161", interval, app, None, "Walk")
        if kind == "walk"
        else PollTaskGenerator("router-01:161", interval, app, None, ["A", "B"], 120)
    )
    data = generator.generate_task_definition()
    manager = customtaskmanager.CustomPeriodicTaskManager()
    manager.manage_task(initial_registration=True, **data)
    return (
        manager,
        data,
        RedBeatSchedulerEntry.from_key("redbeat:" + data["name"], app=app),
    )


@pytest.mark.parametrize("window", [1, 60, 86400])
@pytest.mark.parametrize("interval", [1, 10, 60, 300, 301, 600, 1800, 86400])
@pytest.mark.parametrize("kind", ["walk", "poll"])
def test_window_boundaries_and_three_reservations(
    app, monkeypatch, window, interval, kind
):
    from splunk_connect_for_snmp.common.polling_jitter import (
        JitterSettings,
        calculate_offset,
    )

    _, _, entry = create_entry(app, monkeypatch, kind, interval, window)
    offset, fingerprint = calculate_offset(
        "router-01", 161, interval, kind, JitterSettings(True, window)
    )
    assert 1 <= offset <= min(window, interval)
    first = NOW + timedelta(
        seconds=offset + (interval if kind == "poll" and interval <= 300 else 0)
    )
    assert entry.last_run_at == first - timedelta(seconds=interval)
    assert (
        app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key)
        == first.timestamp()
    )
    scheduler = RedBeatScheduler(app, lazy=True, max_interval=86400)
    with app.connection_for_read() as connection:
        queue = connection.SimpleQueue(app.conf.task_default_queue)
        try:
            for cycle in range(3):
                due = first + timedelta(seconds=cycle * interval)
                app.now = lambda: due - timedelta(microseconds=1)
                scheduler.tick()
                assert read_message(queue) is None
                app.now = lambda: due
                scheduler.tick()
                message = read_message(queue)
                assert message is not None
                assert message.headers.get("expires") is not None
                assert message.payload[1].get("_schedule_context") == (
                    "initial_registration" if kind == "walk" and cycle == 0 else None
                )
                message.ack()
                assert read_message(queue) is None
                stored = RedBeatSchedulerEntry.from_key(entry.key, app=app)
                assert stored.total_run_count == cycle + 1
                assert stored.jitter_fingerprint == fingerprint
                assert (
                    app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key)
                    == (due + timedelta(seconds=interval)).timestamp()
                )
        finally:
            queue.close()
            scheduler.close()


@pytest.mark.parametrize("interval", [60, 300, 301, 600])
def test_refresh_before_first_poll_keeps_existing_threshold(app, monkeypatch, interval):
    manager, data, entry = create_entry(app, monkeypatch, interval=interval)
    score = app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key)
    manager.manage_task(**data)
    stored = RedBeatSchedulerEntry.from_key(entry.key, app=app)
    if interval <= 300:
        assert (
            app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key) == score
        )
        assert not stored.is_due()[0]
        assert not app.redbeat_redis.sismember("run_immediately", entry.key)
    else:
        assert stored.is_due()[0]
        assert app.redbeat_redis.sismember("run_immediately", entry.key)
        scheduler = RedBeatScheduler(app, lazy=True)
        with patch.object(app, "send_task") as publish:
            scheduler.tick()
        assert publish.call_count == 1
        stored = RedBeatSchedulerEntry.from_key(entry.key, app=app)
        assert stored.last_run_at == NOW
        assert (
            app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key)
            == (NOW + timedelta(seconds=interval)).timestamp()
        )


def test_urgent_walk_overrides_initial_phase(app, monkeypatch):
    manager, data, entry = create_entry(app, monkeypatch, "walk", 1800)
    manager.manage_task(name=data["name"], run_immediately=True)
    stored = RedBeatSchedulerEntry.from_key(entry.key, app=app)
    assert stored.is_due()[0]
    assert "_schedule_context" not in stored.kwargs
    assert stored.first_run_kwargs == {}
    scheduler = RedBeatScheduler(app, lazy=True)
    with patch.object(app, "send_task") as publish:
        scheduler.tick()
    assert publish.call_count == 1
    assert "_schedule_context" not in publish.call_args.args[2]
    assert (
        app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key)
        == (NOW + timedelta(seconds=1800)).timestamp()
    )


@pytest.mark.parametrize("kind", ["walk", "poll"])
@pytest.mark.parametrize("confirmed,enabled", [(False, "true"), (True, "false")])
def test_recovery_and_disabled_creation_have_no_feature_state(
    app, monkeypatch, kind, confirmed, enabled
):
    from splunk_connect_for_snmp import customtaskmanager
    from splunk_connect_for_snmp.common.task_generator import (
        PollTaskGenerator,
        WalkTaskGenerator,
    )

    monkeypatch.setattr(
        polling_jitter, "JITTER_SETTINGS", JitterSettings(enabled == "true", 60)
    )
    monkeypatch.setattr(customtaskmanager, "app", app)
    app.now = lambda: NOW
    generator = (
        WalkTaskGenerator("router-01:161", 1800, app, None, "Walk")
        if kind == "walk"
        else PollTaskGenerator("router-01:161", 60, app, None, ["A"], 120)
    )
    data = generator.generate_task_definition()
    customtaskmanager.CustomPeriodicTaskManager().manage_task(
        initial_registration=confirmed, **data
    )
    key = "redbeat:" + data["name"]
    stored = RedBeatSchedulerEntry.from_key(key, app=app)
    assert not app.redbeat_redis.hexists(key, "jitter_fingerprint")
    assert "_schedule_context" not in stored.kwargs
    assert not app.redbeat_redis.hexists(key, "jitter_pending_request")


def test_initial_walk_payload_update_preserves_first_invocation_state(app, monkeypatch):
    manager, data, entry = create_entry(app, monkeypatch, "walk", 1800)
    score = app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key)
    data["kwargs"]["profile"] = "UpdatedWalk"
    data["run_immediately"] = False
    manager.manage_task(**data)
    updated = RedBeatSchedulerEntry.from_key(entry.key, app=app)
    assert updated.kwargs["profile"] == "UpdatedWalk"
    assert "_schedule_context" not in updated.kwargs
    assert updated.first_run_kwargs == {"_schedule_context": "initial_registration"}
    assert updated.last_run_at == entry.last_run_at
    assert updated.total_run_count == entry.total_run_count
    assert app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key) == score
    app.now = lambda: datetime.fromtimestamp(score, timezone.utc)
    invocation = next(updated)
    assert invocation.kwargs["_schedule_context"] == "initial_registration"
    saved = RedBeatSchedulerEntry.from_key(entry.key, app=app)
    assert saved.first_run_kwargs == {}
    assert "_schedule_context" not in saved.kwargs


def test_global_rewalk_cancels_pending_first_invocation_state(app, monkeypatch):
    manager, _, entry = create_entry(app, monkeypatch, "walk", 1800)
    manager.rerun_all_walks()
    saved = RedBeatSchedulerEntry.from_key(entry.key, app=app)
    assert saved.is_due()[0]
    assert saved.first_run_kwargs == {}
    assert "_schedule_context" not in saved.kwargs
    scheduler = RedBeatScheduler(app, lazy=True)
    with patch.object(app, "send_task") as publish:
        scheduler.tick()
    assert publish.call_count == 1
    assert "_schedule_context" not in publish.call_args.args[2]
    assert (
        app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key)
        == (NOW + timedelta(seconds=1800)).timestamp()
    )


@pytest.mark.parametrize("kind,interval", [("walk", 1800), ("poll", 60)])
def test_debug_offset_matches_persisted_first_due(
    app, monkeypatch, caplog, kind, interval
):
    with caplog.at_level(
        logging.DEBUG, logger="splunk_connect_for_snmp.customtaskmanager"
    ):
        _, _, entry = create_entry(app, monkeypatch, kind, interval)
    records = [
        r
        for r in caplog.records
        if r.getMessage().startswith("Applied polling jitter:")
    ]
    assert len(records) == 1
    record = records[0]
    assert record.levelno == logging.DEBUG
    due = entry.last_run_at + timedelta(seconds=interval)
    offset = int((due - NOW).total_seconds()) - (interval if kind == "poll" else 0)
    message = record.getMessage()
    assert f"schedule={entry.name} " in message
    assert f"interval_seconds={interval} " in message
    assert "window_seconds=60 effective_window_seconds=60 " in message
    assert f"offset_seconds={offset} first_due_utc={due.isoformat()}" in message
    assert entry.jitter_fingerprint not in message
    assert "community" not in message and "password" not in message


@pytest.mark.parametrize(
    "kind,interval,delay",
    [("walk", 1800, 35), ("poll", 60, 102), ("poll", 300, 356), ("poll", 600, 22)],
)
def test_sc4snmp_manager_preserves_chain_when_publishing(
    app, monkeypatch, kind, interval, delay
):
    from splunk_connect_for_snmp import customtaskmanager
    from splunk_connect_for_snmp.common.task_generator import (
        PollTaskGenerator,
        WalkTaskGenerator,
    )

    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", JitterSettings(True, 60))
    monkeypatch.setattr(customtaskmanager, "app", app)
    app.now = lambda: NOW
    if kind == "walk":
        data = WalkTaskGenerator(
            "router-01:161", interval, app, None, "WalkProfile"
        ).generate_task_definition()
    else:
        data = PollTaskGenerator(
            "router-01:161", interval, app, None, ["A", "B"], 120
        ).generate_task_definition()
    manager = customtaskmanager.CustomPeriodicTaskManager()
    manager.manage_task(initial_registration=True, **data)
    key = "redbeat:" + data["name"]
    due = NOW + timedelta(seconds=delay)
    assert app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, key) == to_timestamp(
        due
    )
    scheduler = RedBeatScheduler(app, lazy=True, max_interval=3600)
    with app.connection_for_read() as connection:
        queue = connection.SimpleQueue(app.conf.task_default_queue)
        try:
            app.now = lambda: due - timedelta(microseconds=1)
            scheduler.tick()
            assert read_message(queue) is None
            app.now = lambda: due
            # No real polling task is imported or executed. Beat publishes its
            # ordinary signature and complete existing success callbacks.
            with patch.object(app, "send_task", wraps=app.send_task) as publish:
                scheduler.tick()
            publish.assert_called_once()
            message = read_message(queue)
            assert message is not None
            assert message.headers["task"] == data["task"]
            assert message.payload[1]["address"] == "router-01:161"
            callbacks = json.dumps(message.payload[2]["callbacks"])
            assert "splunk_connect_for_snmp.enrich.tasks.enrich" in callbacks
            assert "splunk_connect_for_snmp.splunk.tasks.prepare" in callbacks
            assert "splunk_connect_for_snmp.splunk.tasks.send" in callbacks
            if kind == "walk":
                assert (
                    "splunk_connect_for_snmp.inventory.tasks.inventory_setup_poller"
                    in callbacks
                )
                assert message.payload[1]["_schedule_context"] == "initial_registration"
            else:
                assert "_schedule_context" not in message.payload[1]
                assert set(message.payload[1]["profiles"]) == {"A", "B"}
            message.ack()
            assert app.redbeat_redis.hget(key, "jitter_fingerprint")
            assert (
                "_schedule_context"
                not in RedBeatSchedulerEntry.from_key(key, app).kwargs
            )
        finally:
            queue.close()
            scheduler.close()
