"""Exercise documented profile and group paths with real private Redis storage."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from bson.int64 import Int64
from redbeat.schedulers import RedBeatSchedulerEntry

from splunk_connect_for_snmp import customtaskmanager
from splunk_connect_for_snmp.common import inventory_processor, polling_jitter
from splunk_connect_for_snmp.common.collection_manager import ProfilesManager
from splunk_connect_for_snmp.common.inventory_record import InventoryRecord
from splunk_connect_for_snmp.common.polling_jitter import (
    JitterSettings,
    calculate_offset,
)
from splunk_connect_for_snmp.inventory import tasks

NOW = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
ADDRESS = "192.0.2.10:161"


def configure_app(app, monkeypatch):
    """Use a fixed clock and private Redis for actual SC4SNMP schedule writes."""
    app.now = lambda: NOW
    monkeypatch.setattr(customtaskmanager, "app", app)
    monkeypatch.setattr(tasks, "app", app)
    monkeypatch.setattr(inventory_processor, "app", app)
    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", JitterSettings(True, 60))


def inventory_record(profiles="static", smart=True, address="192.0.2.10", port=161):
    """
    Build a validated inventory record without requiring DNS or SNMP access.
    """
    return InventoryRecord(
        address=address,
        port=port,
        version="2c",
        community="test-only-community",
        walk_interval=1800,
        profiles=profiles,
        smart_profiles=smart,
        delete=False,
    )


def configure_mongo(monkeypatch, profiles, ir, records=()):
    """
    Replace database queries while retaining real profile assignment logic
    """
    ProfilesManager.validate_elements(profiles)
    database = MagicMock()
    database.profiles.find.return_value = [
        {name: body} for name, body in profiles.items()
    ]
    database.inventory.find_one.return_value = ir.asdict()
    database.targets.find_one.return_value = {
        "state": {"SNMPv2-MIB|sysDescr": {"value": "Linux test agent"}}
    }
    database.attributes.find.return_value = list(records)
    mongo = MagicMock()
    mongo.sc4snmp = database
    mongo.__getitem__.return_value = database
    monkeypatch.setattr(tasks, "get_mongo_client", lambda: mongo)
    return database


def saved_poll(app, frequency, address=ADDRESS):
    """
    Load the ordinary device-frequency schedule written by poller setup.
    """
    return RedBeatSchedulerEntry.from_key(
        f"redbeat:sc4snmp;{address};{frequency};poll", app=app
    )


def assert_phase(app, entry, interval, address="192.0.2.10", port=161, kind="poll"):
    """
    Compare saved timing with the deterministic identity and first-run rule.
    """
    offset, fingerprint = calculate_offset(
        address, port, interval, kind, JitterSettings(True, 60)
    )
    wait = interval if kind == "poll" and interval <= 300 else 0
    due = NOW + timedelta(seconds=wait + offset)
    assert entry.jitter_fingerprint == fingerprint
    assert entry.last_run_at == due - timedelta(seconds=interval)
    assert (
        app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, entry.key)
        == due.timestamp()
    )
    assert not app.redbeat_redis.sismember("run_immediately", entry.key)


@pytest.mark.parametrize(
    "smart,base_enabled", [(True, True), (True, False), (False, True), (False, False)]
)
def test_profile_assignment_and_frequency_grouping(
    app, monkeypatch, smart, base_enabled
):
    configure_app(app, monkeypatch)
    monkeypatch.setattr(tasks, "POLL_BASE_PROFILES", base_enabled)
    vb = [["SNMPv2-MIB", "sysName", 0]]
    profiles = {
        "static": {"frequency": 60, "varBinds": vb},
        "base": {"frequency": 60, "varBinds": vb, "condition": {"type": "base"}},
        "field": {
            "frequency": 60,
            "varBinds": vb,
            "condition": {
                "type": "field",
                "field": "SNMPv2-MIB.sysDescr",
                "patterns": ["Linux.*"],
            },
        },
        "nonmatching": {
            "frequency": 180,
            "varBinds": vb,
            "condition": {
                "type": "field",
                "field": "SNMPv2-MIB.sysDescr",
                "patterns": ["Windows.*"],
            },
        },
        "mandatory": {
            "frequency": 120,
            "varBinds": vb,
            "condition": {"type": "mandatory"},
        },
        "walk_scope": {"varBinds": [["UDP-MIB"]], "condition": {"type": "walk"}},
    }
    configure_mongo(monkeypatch, profiles, inventory_record("static;walk_scope", smart))
    tasks.inventory_setup_poller.run(
        {
            "address": ADDRESS,
            "_schedule_context": "initial_registration",
            "chain_of_tasks_expiry_time": 120,
        }
    )
    entry = saved_poll(app, 60)
    expected = {"static"}
    if smart:
        expected.add("field")
        if base_enabled:
            expected.add("base")
    assert set(entry.kwargs["profiles"]) == expected
    assert saved_poll(app, 120).kwargs["profiles"] == ["mandatory"]
    assert len(list(app.redbeat_redis.scan_iter("redbeat:sc4snmp;*"))) == 2
    assert_phase(app, entry, 60)
    assert_phase(app, saved_poll(app, 120), 120)


@pytest.mark.parametrize("indexes", [[1, 7], []])
def test_conditional_profile_keeps_selected_varbinds(app, monkeypatch, indexes):
    configure_app(app, monkeypatch)
    profile = {
        "frequency": 60,
        "conditions": [
            {"field": "IF-MIB.ifAdminStatus", "operation": "equals", "value": "up"}
        ],
        "varBinds": [["IF-MIB", "ifDescr"], ["IF-MIB", "ifInErrors"]],
    }
    database = configure_mongo(
        monkeypatch,
        {"conditional": profile},
        inventory_record("conditional", False),
        [{"indexes": [index]} for index in indexes],
    )
    tasks.inventory_setup_poller.run(
        {
            "address": ADDRESS,
            "_schedule_context": "initial_registration",
            "chain_of_tasks_expiry_time": 120,
        }
    )
    generated_name = "conditional__192|0|2|10:161"
    generated = database.profiles.replace_one.call_args.args[1][generated_name]
    assert generated["varBinds"] == [
        varbind + [index] for index in indexes for varbind in profile["varBinds"]
    ]
    query = database.attributes.find.call_args.args[0]
    assert query["$and"][0] == {"address": ADDRESS}
    assert query["$and"][2] == {"fields.IF-MIB|ifAdminStatus.value": {"$eq": "up"}}
    entry = saved_poll(app, 60)
    assert entry.kwargs["profiles"] == [generated_name]
    assert_phase(app, entry, 60)


@pytest.mark.parametrize("frequency", [60.0, Int64(60)])
@pytest.mark.parametrize(
    "kind", ["static", "base", "field", "mandatory", "conditional"]
)
def test_schema_supported_integral_frequency_can_be_phased(
    app, monkeypatch, frequency, kind
):
    configure_app(app, monkeypatch)
    monkeypatch.setattr(tasks, "POLL_BASE_PROFILES", True)
    profile = {"frequency": frequency, "varBinds": [["IF-MIB", "ifDescr"]]}
    if kind in ("base", "mandatory"):
        profile["condition"] = {"type": kind}
    elif kind == "field":
        profile["condition"] = {
            "type": "field",
            "field": "SNMPv2-MIB.sysDescr",
            "patterns": ["Linux.*"],
        }
    elif kind == "conditional":
        profile["conditions"] = [
            {"field": "IF-MIB.ifAdminStatus", "operation": "equals", "value": "up"}
        ]
    profiles = {"selected": profile}
    configure_mongo(
        monkeypatch,
        profiles,
        inventory_record("selected" if kind in ("static", "conditional") else "", True),
        [{"indexes": [1]}],
    )
    assert "selected" in profiles, "This input must pass the existing profile schemas"
    tasks.inventory_setup_poller.run(
        {
            "address": ADDRESS,
            "_schedule_context": "initial_registration",
            "chain_of_tasks_expiry_time": 120,
        }
    )
    entry = saved_poll(app, frequency)
    assert entry.schedule.run_every == timedelta(seconds=60)
    assert entry.kwargs["frequency"] == frequency
    assert_phase(app, entry, 60)


def test_group_members_receive_device_specific_phases(app, monkeypatch):
    configure_app(app, monkeypatch)
    members = [
        {"address": "192.0.2.10", "port": 161},
        {"address": "192.0.2.11", "port": 1161},
        {"address": "2001:db8::1", "port": 161},
    ]
    groups = MagicMock()
    groups.return_element.return_value = [{"routers": members}]
    processor = inventory_processor.InventoryProcessor(groups, MagicMock())
    processor.process_line(
        {
            "address": "routers",
            "port": "",
            "version": "2c",
            "community": "test-only-community",
            "profiles": "static",
            "walk_interval": "1800",
            "smart_profiles": "false",
        }
    )
    assert len(processor.inventory_records) == len(members)
    manager = customtaskmanager.CustomPeriodicTaskManager()
    for source in processor.inventory_records:
        ir = InventoryRecord(**source)
        definition = inventory_processor.gen_walk_task(
            ir, "WalkProfile", source["group"]
        )
        manager.manage_task(initial_registration=True, **definition)
        entry = RedBeatSchedulerEntry.from_key("redbeat:" + definition["name"], app=app)
        assert entry.kwargs["group"] == "routers"
        assert entry.kwargs["address"] == f"{ir.address}:{ir.port}"
        assert_phase(app, entry, 1800, ir.address, ir.port, "walk")


@pytest.mark.parametrize("full_walk,expected", [(False, "second_walk"), (True, None)])
def test_walk_scope_selection_does_not_change_when_phased(
    app, monkeypatch, full_walk, expected
):
    configure_app(app, monkeypatch)
    monkeypatch.setattr(inventory_processor, "ENABLE_FULL_WALK", full_walk)
    profiles = {
        "first_walk": {"condition": {"type": "walk"}, "varBinds": [["IF-MIB"]]},
        "second_walk": {"condition": {"type": "walk"}, "varBinds": [["UDP-MIB"]]},
    }
    manager = inventory_processor.InventoryRecordManager(
        MagicMock(), customtaskmanager.CustomPeriodicTaskManager()
    )
    selected = manager.return_walk_profile(profiles, ["first_walk", "second_walk"])
    assert selected == expected
    definition = inventory_processor.gen_walk_task(
        inventory_record("first_walk;second_walk"), selected
    )
    manager.periodic_object_collection.manage_task(
        initial_registration=True, **definition
    )
    entry = RedBeatSchedulerEntry.from_key("redbeat:" + definition["name"], app=app)
    assert entry.kwargs["profile"] == expected
    assert_phase(app, entry, 1800, kind="walk")


def test_same_frequency_profile_update_preserves_saved_phase(app, monkeypatch):
    configure_app(app, monkeypatch)
    profiles = {"static": {"frequency": 60, "varBinds": [["SNMPv2-MIB", "sysName", 0]]}}
    database = configure_mongo(monkeypatch, profiles, inventory_record("static", False))
    tasks.inventory_setup_poller.run(
        {
            "address": ADDRESS,
            "_schedule_context": "initial_registration",
            "chain_of_tasks_expiry_time": 120,
        }
    )
    before = saved_poll(app, 60)
    score = app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, before.key)
    profiles["additional"] = {
        "frequency": 60,
        "varBinds": [["SNMPv2-MIB", "sysLocation", 0]],
    }
    database.profiles.find.return_value = [
        {name: body} for name, body in profiles.items()
    ]
    database.inventory.find_one.return_value = inventory_record(
        "static;additional", False
    ).asdict()
    tasks.inventory_setup_poller.run(
        {"address": ADDRESS, "chain_of_tasks_expiry_time": 120}
    )
    after = saved_poll(app, 60)
    assert set(after.kwargs["profiles"]) == {"static", "additional"}
    assert after.jitter_fingerprint == before.jitter_fingerprint
    assert after.last_run_at == before.last_run_at
    assert app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, after.key) == score
    assert len(list(app.redbeat_redis.scan_iter("redbeat:sc4snmp;*"))) == 1
