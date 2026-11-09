import copy
import csv
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import yaml
from pymongo.results import UpdateResult
from redbeat.schedulers import RedBeatSchedulerEntry

from splunk_connect_for_snmp import customtaskmanager
from splunk_connect_for_snmp.common import inventory_processor, polling_jitter
from splunk_connect_for_snmp.common.collection_manager import GroupsManager
from splunk_connect_for_snmp.common.inventory_record import InventoryRecord
from splunk_connect_for_snmp.inventory import loader

NOW = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)


def source_record(**changes):
    record = {
        "address": "192.0.2.20",
        "port": "",
        "version": "2c",
        "community": "test-only-community",
        "secret": "",
        "security_engine": "",
        "walk_interval": "1800",
        "profiles": "static",
        "smart_profiles": "false",
        "max_oid_to_process": "",
        "delete": "false",
    }
    record.update(changes)
    return record


def write_inventory(path, records):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def entry_key(address, port=161):
    return f"redbeat:sc4snmp;{address}:{port};walk"


def saved_state(app, key):
    return (
        app.redbeat_redis.hgetall(key),
        app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, key),
        app.redbeat_redis.sismember("run_immediately", key),
    )


@pytest.fixture(params=[False, True], ids=["disabled", "enabled"])
def inventory_environment(app, monkeypatch, request):
    monkeypatch.setattr(customtaskmanager, "app", app)
    monkeypatch.setattr(inventory_processor, "app", app)
    monkeypatch.setattr(
        polling_jitter,
        "JITTER_SETTINGS",
        polling_jitter.JitterSettings(request.param, 60),
    )
    app.now = lambda: NOW
    mongo = MagicMock()
    records = {}

    def find_inventory(query, projection=None):
        return copy.deepcopy(records.get((query["address"], query["port"])))

    def update_inventory(query, update, upsert=False):
        identity = (query["address"], query["port"])
        previous = records.get(identity)
        record = copy.deepcopy(update["$set"])
        records[identity] = record
        return UpdateResult(
            {
                "n": 1,
                "nModified": int(previous is not None and previous != record),
                **({"upserted": "test-only-id"} if previous is None else {}),
            },
            True,
        )

    def delete_inventory(query):
        records.pop((query["address"], query["port"]), None)

    mongo.sc4snmp.inventory.find_one.side_effect = find_inventory
    mongo.sc4snmp.inventory.update_one.side_effect = update_inventory
    mongo.sc4snmp.inventory.delete_one.side_effect = delete_inventory
    manager = inventory_processor.InventoryRecordManager(
        mongo, customtaskmanager.CustomPeriodicTaskManager()
    )
    profiles = {"static": {"frequency": 60, "varBinds": [["SNMPv2-MIB", "sysName", 0]]}}

    def apply(records_to_apply, removed=()):
        return loader.manage_inventory_records(
            profiles, False, removed, False, records_to_apply, manager, mongo
        )

    return SimpleNamespace(
        app=app,
        enabled=request.param,
        mongo=mongo,
        records=records,
        manager=manager,
        apply=apply,
    )


@pytest.mark.parametrize("from_mongo", [False, True], ids=["csv", "mongo"])
def test_inventory_sources_create_update_delete_and_readd(
    inventory_environment, monkeypatch, tmp_path, from_mongo
):
    env = inventory_environment
    path = tmp_path / "inventory.csv"
    monkeypatch.setattr(inventory_processor, "INVENTORY_PATH", str(path))
    monkeypatch.setattr(inventory_processor, "CONFIG_FROM_MONGO", from_mongo)
    monkeypatch.setattr(loader, "CONFIG_FROM_MONGO", from_mongo)

    def read_records(record):
        write_inventory(path, [record])
        env.mongo.sc4snmp.inventory_ui.find.return_value = [copy.deepcopy(record)]
        processor = inventory_processor.InventoryProcessor(
            MagicMock(), env.mongo.sc4snmp.inventory_ui
        )
        return processor.get_all_hosts()[0]

    source = source_record()
    assert not env.apply(read_records(source))
    key = entry_key(source["address"])
    before = saved_state(env.app, key)
    initial = RedBeatSchedulerEntry.from_key(key, app=env.app)
    assert bool(initial.jitter_fingerprint) is env.enabled
    assert not env.apply(read_records(source))
    assert saved_state(env.app, key) == before

    # Omitting a record keeps the saved device. Its delete flag removes it.
    assert not env.apply([])
    assert env.app.redbeat_redis.exists(key)
    env.app.now = lambda: NOW + timedelta(minutes=5)
    source["community"] = "replacement-test-only-community"
    assert not env.apply(read_records(source))
    updated = RedBeatSchedulerEntry.from_key(key, app=env.app)
    assert updated.jitter_fingerprint == initial.jitter_fingerprint
    assert len(env.records) == 1
    source["delete"] = "true"
    assert not env.apply(read_records(source))
    assert not env.app.redbeat_redis.exists(key)
    assert not env.records
    if from_mongo:
        env.mongo.sc4snmp.inventory_ui.delete_one.assert_called_once_with(
            {"address": source["address"], "port": 161}
        )
    source["delete"] = "false"
    assert not env.apply(read_records(source))
    readded = RedBeatSchedulerEntry.from_key(key, app=env.app)
    assert readded.jitter_fingerprint == initial.jitter_fingerprint
    assert readded.total_run_count == 0


def test_switch_inventory_sources_preserves_existing_schedule(
    inventory_environment, monkeypatch, tmp_path
):
    env = inventory_environment
    path = tmp_path / "inventory.csv"
    config_path = tmp_path / "config.yaml"
    record = source_record()
    write_inventory(path, [record])
    config_path.write_text(
        yaml.safe_dump(
            {
                "groups": {},
                "profiles": {
                    "static": {
                        "frequency": 60,
                        "varBinds": [["SNMPv2-MIB", "sysName", 0]],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(inventory_processor, "INVENTORY_PATH", str(path))
    monkeypatch.setattr(loader, "INVENTORY_PATH", str(path))
    monkeypatch.setattr(loader, "CONFIG_PATH", str(config_path))
    monkeypatch.setattr(inventory_processor, "CONFIG_FROM_MONGO", False)
    monkeypatch.setattr(loader, "CONFIG_FROM_MONGO", False)
    file_records, _ = inventory_processor.InventoryProcessor(
        MagicMock(), env.mongo.sc4snmp.inventory_ui
    ).get_all_hosts()
    assert not env.apply(file_records)
    key = entry_key(record["address"])
    before = saved_state(env.app, key)

    env.mongo.sc4snmp.used_ui.find_one.return_value = None
    monkeypatch.setattr(loader, "CONFIG_FROM_MONGO", True)
    loader.configure_ui_database(env.mongo)
    seeded = env.mongo.sc4snmp.inventory_ui.insert_many.call_args.args[0]
    env.mongo.sc4snmp.inventory_ui.find.return_value = seeded
    monkeypatch.setattr(inventory_processor, "CONFIG_FROM_MONGO", True)
    mongo_records, _ = inventory_processor.InventoryProcessor(
        MagicMock(), env.mongo.sc4snmp.inventory_ui
    ).get_all_hosts()
    assert not env.apply(mongo_records)
    assert saved_state(env.app, key) == before

    env.mongo.sc4snmp.used_ui.find_one.return_value = {"used_ui": True}
    monkeypatch.setattr(loader, "CONFIG_FROM_MONGO", False)
    monkeypatch.setattr(inventory_processor, "CONFIG_FROM_MONGO", False)
    loader.configure_ui_database(env.mongo)
    for collection in ("inventory_ui", "groups_ui", "profiles_ui"):
        getattr(env.mongo.sc4snmp, collection).drop.assert_called_once_with()
    assert not env.apply(file_records)
    assert saved_state(env.app, key) == before


@pytest.mark.parametrize("field", ["port", "max_oid_to_process"])
def test_supported_optional_omission_and_blank_keep_same_schedule(
    inventory_environment, field
):
    env = inventory_environment
    record = source_record()
    omitted = {key: value for key, value in record.items() if key != field}
    assert not env.apply([omitted])
    key = entry_key(record["address"])
    before = saved_state(env.app, key)
    assert not env.apply([record])
    assert saved_state(env.app, key) == before
    saved_inventory = env.records[(record["address"], 161)]
    assert saved_inventory["port"] == 161
    assert saved_inventory["max_oid_to_process"] is None


def test_group_overrides_and_member_or_group_removal(
    inventory_environment, monkeypatch
):
    env = inventory_environment
    members = [
        {"address": "192.0.2.21"},
        {
            "address": "192.0.2.22",
            "port": 1161,
            "version": "3",
            "secret": "test-only-secret-reference",
            "security_engine": "8000000001",
            "community": "test-only-override",
            "max_oid_to_process": 15,
        },
    ]
    groups = {"test_routers": members}
    GroupsManager.validate_elements(groups)
    assert "test_routers" in groups
    group_manager = MagicMock()
    group_manager.return_element.return_value = [groups]
    monkeypatch.setattr(inventory_processor, "CONFIG_FROM_MONGO", True)
    env.mongo.sc4snmp.inventory_ui.find.return_value = [
        source_record(address="test_routers"),
        source_record(address=members[0]["address"], profiles="not-selected"),
    ]
    records, mapping = inventory_processor.InventoryProcessor(
        group_manager, env.mongo.sc4snmp.inventory_ui
    ).get_all_hosts()
    assert len(records) == 2
    assert all(record["profiles"] == "static" for record in records)
    assert not env.apply(records)
    override = env.records[(members[1]["address"], 1161)]
    for field in (
        "version",
        "secret",
        "security_engine",
        "community",
        "max_oid_to_process",
    ):
        assert override[field] == members[1][field]
    kept_key = entry_key(members[0]["address"])
    removed_key = entry_key(members[1]["address"], 1161)
    kept_state = saved_state(env.app, kept_key)
    reduced = {"test_routers": [members[0]]}
    removed = inventory_processor.return_hosts_from_deleted_groups(
        groups, reduced, mapping
    )
    assert not env.apply([], removed)
    assert not env.app.redbeat_redis.exists(removed_key)
    assert saved_state(env.app, kept_key) == kept_state
    removed = inventory_processor.return_hosts_from_deleted_groups(reduced, {}, mapping)
    assert not env.apply([], removed)
    assert not env.app.redbeat_redis.exists(kept_key)
    assert not env.records


@pytest.mark.parametrize("address", ["192.0.2.23", "2001:db8::23", "localhost"])
def test_address_ports_and_credentials_keep_identity_separate(
    inventory_environment, address
):
    env = inventory_environment
    records = [source_record(address=address, port=str(port)) for port in (161, 1161)]
    assert not env.apply(records)
    entries = [
        RedBeatSchedulerEntry.from_key(entry_key(address, port), app=env.app)
        for port in (161, 1161)
    ]
    assert entries[0].key != entries[1].key
    if env.enabled:
        assert entries[0].jitter_fingerprint != entries[1].jitter_fingerprint
    other_port_state = saved_state(env.app, entries[1].key)
    env.app.now = lambda: NOW + timedelta(minutes=5)
    changed = source_record(
        address=address,
        version="3",
        secret="replacement-test-only-secret-reference",
        community="replacement-test-only-community",
        security_engine="8000000002",
    )
    assert not env.apply([changed])
    updated = RedBeatSchedulerEntry.from_key(entry_key(address), app=env.app)
    assert updated.jitter_fingerprint == entries[0].jitter_fingerprint
    assert saved_state(env.app, entries[1].key) == other_port_state
    assert len(env.records) == 2
    assert "secret" not in updated.kwargs
    assert "community" not in updated.kwargs
    assert InventoryRecord(**changed).version == "3"
