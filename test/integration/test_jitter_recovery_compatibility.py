from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from redbeat.schedulers import RedBeatSchedulerEntry
from test_managed_jitter_requests import saved
from test_polling_jitter_integration import NOW, create_entry

from splunk_connect_for_snmp import customtaskmanager
from splunk_connect_for_snmp.common import (
    inventory_processor,
    polling_jitter,
)
from splunk_connect_for_snmp.common.polling_jitter import (
    JitterSettings,
    calculate_offset,
)
from splunk_connect_for_snmp.common.task_generator import WalkTaskGenerator
from splunk_connect_for_snmp.inventory import tasks


@pytest.fixture
def manager(app, monkeypatch):
    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", JitterSettings(True, 60))
    monkeypatch.setattr(customtaskmanager, "app", app)
    monkeypatch.setattr(inventory_processor, "app", app)
    monkeypatch.setattr(tasks, "app", app)
    app.now = lambda: NOW
    return customtaskmanager.CustomPeriodicTaskManager()


def record():
    return SimpleNamespace(
        address="router-01",
        port=161,
        walk_interval=1800,
        profiles=["A"],
        smart_profiles=False,
        asdict=lambda: {"address": "router-01", "port": 161},
    )


def inventory_mongo(retained, modified=0):
    mongo = MagicMock()
    mongo.sc4snmp.inventory.find_one.return_value = (
        {"_id": "existing-record"} if retained else None
    )
    mongo.sc4snmp.inventory.update_one.return_value = SimpleNamespace(
        matched_count=int(retained), modified_count=modified, upserted_id=None
    )
    return mongo


def register_inventory(manager, mongo, expiry=False):
    processor = inventory_processor.InventoryRecordManager(mongo, manager)
    processor.update(record(), {"profiles": "A", "walk_interval": "1800"}, {}, expiry)
    return processor


def assert_legacy(app, entry):
    assert not app.redbeat_redis.hexists(entry.key, "jitter_fingerprint")
    assert entry.first_run_kwargs == {}
    assert "_schedule_context" not in entry.kwargs


@pytest.mark.parametrize("modified", [0, 1])
def test_retained_inventory_missing_walk_rebuilds_without_jitter(
    app, monkeypatch, manager, modified
):
    mongo = inventory_mongo(True, modified)
    register_inventory(manager, mongo)
    entry = RedBeatSchedulerEntry.from_key(
        "redbeat:sc4snmp;router-01:161;walk", app=app
    )
    assert_legacy(app, entry)
    assert entry.is_due()[0]
    assert entry.kwargs["profile"] == "WalkProfile"
    assert entry.options["link"]
    invocation = next(entry)
    assert "_schedule_context" not in invocation.kwargs
    assert saved(entry).last_run_at == NOW
    assert (
        app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key)
        == (NOW + timedelta(seconds=1800)).timestamp()
    )


@pytest.mark.parametrize("managed", [False, True])
def test_retained_walk_with_new_inventory_is_not_first_registration(
    app, monkeypatch, manager, managed
):
    if managed:
        _, _, entry = create_entry(app, monkeypatch, "walk", 1800)
        fingerprint = entry.jitter_fingerprint
    else:
        definition = WalkTaskGenerator(
            "router-01:161", 1800, app, None, "Walk"
        ).generate_task_definition()
        manager.manage_task(**definition)
        entry = RedBeatSchedulerEntry.from_key("redbeat:" + definition["name"], app=app)
    app.now = lambda: NOW + timedelta(minutes=2)
    register_inventory(manager, inventory_mongo(False))
    updated = saved(entry)
    assert updated.first_run_kwargs == entry.first_run_kwargs
    assert "_schedule_context" not in updated.kwargs
    if managed:
        assert updated.jitter_fingerprint == fingerprint
        assert updated._strtobool(updated.run_immediately)
        assert updated.last_run_at == entry.last_run_at
        assert updated.is_due()[0]
    else:
        assert_legacy(app, updated)
        assert updated.is_due()[0]


def test_expiry_recreation_discards_old_jitter_and_keeps_new_task_options(
    app, monkeypatch, manager
):
    from splunk_connect_for_snmp.common import task_generator

    _, _, walk = create_entry(app, monkeypatch, "walk", 1800)
    _, _, poll = create_entry(app, monkeypatch, interval=600)
    new_expiry = walk.options["expires"] + 60
    assert manager.did_expiry_time_change(
        new_expiry, [customtaskmanager.WALK_TASK, customtaskmanager.POLL_TASK]
    )
    assert not app.redbeat_redis.exists(walk.key)
    assert not app.redbeat_redis.exists(poll.key)
    monkeypatch.setattr(task_generator, "CHAIN_OF_TASKS_EXPIRY_TIME", new_expiry)
    monkeypatch.setattr(
        WalkTaskGenerator,
        "WALK_CHAIN_OF_TASKS",
        {**WalkTaskGenerator.WALK_CHAIN_OF_TASKS, "expires": new_expiry},
    )
    register_inventory(manager, inventory_mongo(True), expiry=True)
    entry = saved(walk)
    assert_legacy(app, entry)
    assert entry.options["expires"] == new_expiry
    assert entry.kwargs["chain_of_tasks_expiry_time"] == new_expiry
    assert entry.is_due()[0]


def test_later_walk_recreates_missing_polls_without_offsets(app, monkeypatch, manager):
    profiles = {
        name: {"frequency": frequency, "varBinds": [["SNMPv2-MIB", "sysName", 0]]}
        for name, frequency in (("A", 60), ("B", 300), ("C", 301), ("D", 600))
    }
    ir = record()
    ir.profiles = list(profiles)
    mongo = MagicMock()
    mongo.__getitem__.return_value = mongo.sc4snmp
    mongo.sc4snmp.targets.find_one.return_value = {"state": {}}
    monkeypatch.setattr(tasks, "get_mongo_client", lambda: mongo)
    monkeypatch.setattr(tasks, "get_inventory", lambda *args: ir)
    monkeypatch.setattr(
        tasks.ProfilesManager, "return_collection", lambda self: profiles
    )
    tasks.inventory_setup_poller.run(
        {"address": "router-01:161", "chain_of_tasks_expiry_time": 120}
    )
    for interval in (60, 300, 301, 600):
        entry = RedBeatSchedulerEntry.from_key(
            f"redbeat:sc4snmp;router-01:161;{interval};poll", app=app
        )
        assert_legacy(app, entry)
        assert entry.is_due()[0] is (interval > 300)
        assert entry.options["expires"] == 120
    assert len(list(app.redbeat_redis.scan_iter("redbeat:sc4snmp;*"))) == 4


def test_genuine_device_readdition_keeps_offset_and_uses_new_first_due(
    app, monkeypatch, manager
):
    _, _, original = create_entry(app, monkeypatch, "walk", 1800)
    fingerprint = original.jitter_fingerprint
    offset, _ = calculate_offset(
        "router-01", 161, 1800, "walk", JitterSettings(True, 60)
    )
    processor = inventory_processor.InventoryRecordManager(
        inventory_mongo(False), manager
    )
    processor.delete("router-01:161")
    assert not app.redbeat_redis.exists(original.key)
    baseline = NOW + timedelta(minutes=5)
    app.now = lambda: baseline
    register_inventory(manager, inventory_mongo(False))
    recreated = saved(original)
    assert recreated.jitter_fingerprint == fingerprint
    assert recreated.first_run_kwargs == {"_schedule_context": "initial_registration"}
    assert (
        app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, recreated.key)
        == (baseline + timedelta(seconds=offset)).timestamp()
    )
