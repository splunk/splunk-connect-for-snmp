import runpy
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from celery.schedules import schedule
from redbeat.schedulers import EntryPolicyChanged, RedBeatSchedulerEntry
from test_managed_jitter_requests import reserve_initial, saved
from test_polling_jitter_integration import NOW, create_entry

from splunk_connect_for_snmp import customtaskmanager
from splunk_connect_for_snmp.common import polling_jitter
from splunk_connect_for_snmp.common.polling_jitter import (
    JitterSettings,
    calculate_offset,
    first_due,
)
from splunk_connect_for_snmp.common.task_generator import WalkTaskGenerator
from splunk_connect_for_snmp.jitter_reconcile import apply_entry_policy


def test_inventory_write_crossing_first_adoption_keeps_payload_and_request(
    app, monkeypatch
):
    app.now = lambda: NOW
    monkeypatch.setattr(customtaskmanager, "app", app)
    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", JitterSettings(False, 60))
    manager = customtaskmanager.CustomPeriodicTaskManager()
    data = WalkTaskGenerator(
        "router-01:161", 1800, app, None, "Walk"
    ).generate_task_definition()
    manager.manage_task(**data)
    next(RedBeatSchedulerEntry.from_key("redbeat:" + data["name"], app=app))
    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", JitterSettings(True, 60))
    app.conf.redbeat_entry_policy = apply_entry_policy
    app.now = lambda: NOW + timedelta(minutes=30)
    original = RedBeatSchedulerEntry.save_guarded
    attempts = []

    def overlapping_save(entry, **kwargs):
        attempts.append(entry.key)
        # Beat applies new settings while inventory still holds the old entry.
        app.redbeat_redis.srem("run_immediately", entry.key)
        next(saved(entry))
        assert saved(entry).jitter_fingerprint
        return original(entry, **kwargs)

    monkeypatch.setattr(RedBeatSchedulerEntry, "save_guarded", overlapping_save)
    data["kwargs"]["profile"] = "UpdatedWalk"
    manager.manage_task(inventory_update=True, **data)
    entry = RedBeatSchedulerEntry.from_key("redbeat:" + data["name"], app=app)
    offset, fingerprint = calculate_offset(
        "router-01", 161, 1800, "walk", JitterSettings(True, 60)
    )
    assert attempts == [entry.key]
    assert entry.kwargs["profile"] == "UpdatedWalk"
    assert entry.jitter_fingerprint == fingerprint
    assert entry._strtobool(entry.run_immediately)
    assert entry.last_run_at + entry.schedule.run_every == first_due(app.now(), offset)


@pytest.mark.parametrize("enabled", [True, False])
def test_inventory_request_reloads_a_changed_policy(app, monkeypatch, enabled):
    manager, data, entry = create_entry(app, monkeypatch, "walk", 1800)
    entry = reserve_initial(app, entry)
    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", JitterSettings(enabled, 120))
    app.conf.redbeat_entry_policy = apply_entry_policy
    ordinary_due = entry.last_run_at + entry.schedule.run_every
    app.now = lambda: ordinary_due
    original = RedBeatSchedulerEntry.request_run
    attempts = []

    def overlapping_request(loaded, due, **kwargs):
        attempts.append(loaded.jitter_fingerprint)
        if len(attempts) == 1:
            next(saved(loaded))
            updated = saved(loaded)
            assert updated.jitter_fingerprint != loaded.jitter_fingerprint
        return original(loaded, due, **kwargs)

    monkeypatch.setattr(RedBeatSchedulerEntry, "request_run", overlapping_request)
    data["kwargs"]["profile"] = "LatestWalk"
    manager.manage_task(inventory_update=True, **data)
    updated = saved(entry)
    assert len(attempts) == (2 if enabled else 1)
    assert updated.kwargs["profile"] == "LatestWalk"
    if enabled:
        offset, fingerprint = calculate_offset(
            "router-01", 161, 1800, "walk", JitterSettings(True, 120)
        )
        assert updated.jitter_fingerprint == fingerprint
        assert updated.last_run_at + updated.schedule.run_every == first_due(
            app.now(), offset
        )
        assert updated._strtobool(updated.run_immediately)
    else:
        assert updated.jitter_fingerprint is None
        assert updated.is_due()[0]


def test_policy_reload_does_not_recreate_a_deleted_entry(app, monkeypatch):
    manager, data, entry = create_entry(app, monkeypatch, "walk", 1800)

    def delete_before_reload(loaded, *args, **kwargs):
        loaded.delete()
        raise EntryPolicyChanged("The applied policy changed")

    monkeypatch.setattr(RedBeatSchedulerEntry, "request_run", delete_before_reload)
    data["kwargs"] = {**data["kwargs"], "profile": "ObsoleteUpdate"}
    with pytest.raises(KeyError):
        manager.manage_task(inventory_update=True, **data)
    assert not app.redbeat_redis.exists(entry.key)


@pytest.mark.parametrize("legacy_entry", [False, True])
def test_same_key_readdition_rejects_an_older_matching_update(
    app, monkeypatch, legacy_entry
):
    manager, data, entry = create_entry(app, monkeypatch, "walk", 1800)
    if legacy_entry:
        app.redbeat_redis.hdel(entry.key, "entry_id")
        entry = saved(entry)
        assert entry.entry_id is None
    original = RedBeatSchedulerEntry.request_run
    replacement_data = {
        **data,
        "kwargs": {**data["kwargs"], "profile": "ReplacementWalk"},
    }
    first_due_time = entry.last_run_at + entry.schedule.run_every
    replaced = []

    def replace_before_request(loaded, due, **kwargs):
        loaded.delete()
        replacement = RedBeatSchedulerEntry(**replacement_data)
        replacement.save_with_first_due(first_due_time, loaded.jitter_fingerprint)
        replaced.append(
            (
                app.redbeat_redis.hgetall(replacement.key),
                app.redbeat_redis.zscore(
                    app.redbeat_conf.schedule_key, replacement.key
                ),
                app.redbeat_redis.sismember("run_immediately", replacement.key),
            )
        )
        return original(loaded, due, **kwargs)

    monkeypatch.setattr(RedBeatSchedulerEntry, "request_run", replace_before_request)
    data["kwargs"] = {**data["kwargs"], "profile": "OlderInventoryUpdate"}
    with pytest.raises(KeyError):
        manager.manage_task(inventory_update=True, **data)
    updated = saved(entry)
    assert updated.entry_id != entry.entry_id
    assert updated.kwargs["profile"] == "ReplacementWalk"
    assert replaced == [
        (
            app.redbeat_redis.hgetall(entry.key),
            app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key),
            app.redbeat_redis.sismember("run_immediately", entry.key),
        )
    ]


def test_policy_reload_does_not_update_a_same_key_replacement(app, monkeypatch):
    manager, data, entry = create_entry(app, monkeypatch, "walk", 1800)
    original_load = RedBeatSchedulerEntry.from_key
    calls = []
    replacement_state = []

    def load_with_replacement(key, app=None):
        calls.append(key)
        if len(calls) == 2:
            entry.delete()
            replacement_data = {
                **data,
                "kwargs": {**data["kwargs"], "profile": "ReplacementWalk"},
            }
            replacement = RedBeatSchedulerEntry(**replacement_data)
            replacement.save_with_first_due(
                entry.last_run_at + entry.schedule.run_every,
                entry.jitter_fingerprint,
            )
            replacement_state.append(app.redbeat_redis.hgetall(key))
        return original_load(key, app=app)

    def policy_changed(loaded, *args, **kwargs):
        raise EntryPolicyChanged("The applied policy changed")

    monkeypatch.setattr(RedBeatSchedulerEntry, "from_key", load_with_replacement)
    monkeypatch.setattr(RedBeatSchedulerEntry, "request_run", policy_changed)
    data["kwargs"] = {**data["kwargs"], "profile": "OlderInventoryUpdate"}
    with pytest.raises(KeyError):
        manager.manage_task(inventory_update=True, **data)
    assert len(calls) == 2
    assert replacement_state == [app.redbeat_redis.hgetall(entry.key)]
    assert original_load(entry.key, app=app).kwargs["profile"] == "ReplacementWalk"


def test_overlapping_ordinary_creators_keep_the_winning_entry(app, monkeypatch):
    app.now = lambda: NOW
    monkeypatch.setattr(customtaskmanager, "app", app)
    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", JitterSettings(False, 60))
    manager = customtaskmanager.CustomPeriodicTaskManager()
    data = WalkTaskGenerator(
        "router-01:161", 1800, app, None, "Walk"
    ).generate_task_definition()
    original_load = RedBeatSchedulerEntry.from_key
    both_missing = Barrier(2, timeout=5)

    def load_after_both_observe_missing(key, app=None):
        try:
            return original_load(key, app=app)
        except KeyError:
            both_missing.wait()
            raise

    def create(profile):
        task_data = {**data, "kwargs": {**data["kwargs"], "profile": profile}}
        manager.manage_task(**task_data)
        return profile

    monkeypatch.setattr(
        RedBeatSchedulerEntry, "from_key", load_after_both_observe_missing
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(create, profile) for profile in ("First", "Second")]
        outcomes = [future.result(timeout=10) for future in futures]
    winner = original_load("redbeat:" + data["name"], app=app)
    assert outcomes == ["First", "Second"]
    assert winner.kwargs["profile"] in outcomes
    assert winner.entry_id
    assert winner.is_due()[0]


@pytest.mark.parametrize("kind,interval", [("walk", 1800), ("poll", 600)])
@pytest.mark.parametrize("reserved", [False, True])
def test_initial_creation_collision_updates_the_winner_without_rephasing(
    app, monkeypatch, kind, interval, reserved
):
    manager, data, entry = create_entry(app, monkeypatch, kind, interval)
    if reserved:
        entry = reserve_initial(app, entry)
    original_load = RedBeatSchedulerEntry.from_key
    previous_due = app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key)
    previous_meta = app.redbeat_redis.hget(entry.key, "meta")
    loads = []

    def load_after_another_creator(key, app=None):
        loads.append(key)
        if len(loads) == 1:
            raise KeyError(key)
        return original_load(key, app=app)

    monkeypatch.setattr(RedBeatSchedulerEntry, "from_key", load_after_another_creator)
    profile_field = "profile" if kind == "walk" else "profiles"
    latest_profiles = "LatestWalk" if kind == "walk" else ["LatestPoll"]
    data["kwargs"][profile_field] = latest_profiles
    manager.manage_task(initial_registration=True, **data)
    updated = original_load(entry.key, app=app)

    assert updated.entry_id == entry.entry_id
    assert updated.kwargs[profile_field] == latest_profiles
    assert updated.total_run_count == entry.total_run_count
    if reserved:
        assert updated._strtobool(updated.run_immediately)
        assert updated.last_run_at + updated.schedule.run_every == app.now()
    else:
        assert updated.first_run_kwargs == entry.first_run_kwargs
        assert not updated._strtobool(updated.run_immediately)
        assert app.redbeat_redis.hget(entry.key, "meta") == previous_meta
        assert (
            app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key)
            == previous_due
        )


def test_creation_collision_does_not_recreate_an_entry_deleted_before_reload(
    app, monkeypatch
):
    manager, data, entry = create_entry(app, monkeypatch, "walk", 1800)
    original_load = RedBeatSchedulerEntry.from_key
    loads = []

    def delete_before_collision_reload(key, app=None):
        loads.append(key)
        if len(loads) == 1:
            raise KeyError(key)
        entry.delete()
        return original_load(key, app=app)

    monkeypatch.setattr(
        RedBeatSchedulerEntry, "from_key", delete_before_collision_reload
    )
    with pytest.raises(KeyError):
        manager.manage_task(initial_registration=True, **data)
    assert len(loads) == 2
    assert not app.redbeat_redis.exists(entry.key)


def test_recovery_creation_keeps_identity_when_rescheduled(app, monkeypatch):
    app.now = lambda: NOW
    monkeypatch.setattr(customtaskmanager, "app", app)
    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", JitterSettings(True, 60))
    manager = customtaskmanager.CustomPeriodicTaskManager()
    data = WalkTaskGenerator(
        "router-01:161", 1800, app, None, "Walk"
    ).generate_task_definition()
    manager.manage_task(**data)
    entry = RedBeatSchedulerEntry.from_key("redbeat:" + data["name"], app=app)
    assert entry.entry_id
    assert entry.jitter_fingerprint is None
    assert entry.first_run_kwargs == {}
    assert entry.last_run_at == NOW
    assert entry.is_due()[0]
    manager.manage_task(name=data["name"], run_immediately=True)
    updated = saved(entry)
    assert updated.entry_id == entry.entry_id
    assert updated.is_due()[0]


def test_ordinary_creation_does_not_reschedule_a_newer_replacement(app, monkeypatch):
    app.now = lambda: NOW
    monkeypatch.setattr(customtaskmanager, "app", app)
    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", JitterSettings(False, 60))
    manager = customtaskmanager.CustomPeriodicTaskManager()
    data = WalkTaskGenerator(
        "router-01:161", 1800, app, None, "Walk"
    ).generate_task_definition()
    original_save = RedBeatSchedulerEntry.save_guarded
    replacement_state = []

    def replace_after_creation(entry, *, create=False):
        result = original_save(entry, create=create)
        if create:
            entry.delete()
            replacement_data = {
                **data,
                "kwargs": {**data["kwargs"], "profile": "ReplacementWalk"},
            }
            replacement = RedBeatSchedulerEntry(**replacement_data)
            original_save(replacement, create=True)
            replacement_state.append(
                (
                    app.redbeat_redis.hgetall(entry.key),
                    app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key),
                    app.redbeat_redis.sismember("run_immediately", entry.key),
                )
            )
        return result

    monkeypatch.setattr(RedBeatSchedulerEntry, "save_guarded", replace_after_creation)
    manager.manage_task(**data)
    key = "redbeat:" + data["name"]
    assert replacement_state == [
        (
            app.redbeat_redis.hgetall(key),
            app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, key),
            app.redbeat_redis.sismember("run_immediately", key),
        )
    ]
    updated = RedBeatSchedulerEntry.from_key(key, app=app)
    assert updated.kwargs["profile"] == "ReplacementWalk"


def test_policy_reload_is_bounded_and_does_not_retry_other_errors(app, monkeypatch):
    manager, data, entry = create_entry(app, monkeypatch, "walk", 1800)
    attempts = []

    def conflict(loaded, *args, **kwargs):
        attempts.append(loaded.key)
        raise EntryPolicyChanged("The applied policy changed")

    monkeypatch.setattr(RedBeatSchedulerEntry, "request_run", conflict)
    with pytest.raises(EntryPolicyChanged):
        manager.manage_task(inventory_update=True, **data)
    assert len(attempts) == 3

    def changed_interval(loaded, *args, **kwargs):
        attempts.append(loaded.key)
        raise ValueError("The managed schedule interval changed")

    monkeypatch.setattr(RedBeatSchedulerEntry, "request_run", changed_interval)
    attempts.clear()
    with pytest.raises(ValueError, match="interval changed"):
        manager.manage_task(inventory_update=True, **data)
    assert len(attempts) == 1


@pytest.mark.parametrize("adopt_disable", [False, True])
def test_walk_interval_update_after_disable_still_requests_immediately(
    app, monkeypatch, adopt_disable
):
    manager, data, entry = create_entry(app, monkeypatch, "walk", 1800, window=120)
    entry = reserve_initial(app, entry)
    app.now = lambda: NOW + timedelta(minutes=2)
    monkeypatch.setenv("POLLING_JITTER_ENABLED", "false")
    monkeypatch.setenv("POLLING_JITTER_WINDOW_SECONDS", "abc")
    settings = runpy.run_path(polling_jitter.__file__)["JITTER_SETTINGS"]
    assert (settings.enabled, settings.window_seconds) == (False, 60)
    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", settings)
    if adopt_disable:
        app.conf.redbeat_entry_policy = apply_entry_policy
        ordinary_due = entry.last_run_at + entry.schedule.run_every
        app.now = lambda: ordinary_due
        next(saved(entry))
        assert saved(entry).jitter_fingerprint is None
    data["schedule"] = schedule(900, app=app)
    manager.manage_task(inventory_update=True, **data)
    updated = saved(entry)
    assert updated.schedule.run_every == timedelta(seconds=900)
    assert updated._strtobool(updated.run_immediately)
    if not adopt_disable:
        assert updated.last_run_at + updated.schedule.run_every == app.now()
        assert (
            updated.jitter_fingerprint
            == calculate_offset(
                "router-01", 161, 900, "walk", JitterSettings(True, 120)
            )[1]
        )
    assert updated.is_due()[0]
    next(updated)
    assert (
        app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key)
        == (app.now() + timedelta(seconds=900)).timestamp()
    )
