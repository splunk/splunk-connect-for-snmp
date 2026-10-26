import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest
from celery import Celery
from redbeat.schedulers import RedBeatSchedulerEntry

from splunk_connect_for_snmp import customtaskmanager
from splunk_connect_for_snmp.common import polling_jitter
from splunk_connect_for_snmp.common.inventory_processor import InventoryRecordManager
from splunk_connect_for_snmp.common.inventory_record import InventoryRecord
from splunk_connect_for_snmp.common.polling_jitter import (
    INITIAL_REGISTRATION,
    SCHEDULE_CONTEXT,
    JitterSettings,
    PollingJitterError,
)
from splunk_connect_for_snmp.common.task_generator import (
    PollTaskGenerator,
    WalkTaskGenerator,
)

NOW = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)


@pytest.fixture
def app(monkeypatch):
    """
    Create a fixed-clock app without a real broker or storage connection.

    :return: Test Celery app with jitter enabled
    """
    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", JitterSettings(True, 60))
    # Older tests patch __new__, which can leave Python's allocation slot
    # altered even after restoration. Isolate our real-constructor checks.
    monkeypatch.setattr(
        RedBeatSchedulerEntry,
        "__new__",
        staticmethod(lambda cls, *args, **kwargs: object.__new__(cls)),
    )
    result = Celery("initial-jitter-tests", broker="memory://", set_as_current=False)
    result.conf.redbeat_redis_url = "redis://unused/0"
    result.now = lambda: NOW
    monkeypatch.setattr(customtaskmanager, "app", result)
    yield result
    result.close()


def definition(app, kind, interval):
    """
    Generate the existing full task definition for a dummy device.

    :param app: Isolated Celery app
    :param kind: Either walk or poll
    :param interval: Interval in seconds

    :return: Ordinary task definition including its full callback chain
    """
    if kind == "walk":
        return WalkTaskGenerator(
            "router-01:161", interval, app, None, "WalkProfile"
        ).generate_task_definition()
    return PollTaskGenerator(
        "router-01:161", interval, app, None, ["A", "B"], 120
    ).generate_task_definition()


@pytest.mark.parametrize(
    "kind,interval,offset",
    [
        ("walk", 1800, 35),
        ("poll", 60, 42),
        ("poll", 300, 56),
        ("poll", 301, None),
        ("poll", 600, 22),
    ],
)
def test_new_entry_uses_correct_first_run_baseline(app, kind, interval, offset):
    data = definition(app, kind, interval)
    initial = RedBeatSchedulerEntry(**data)
    with patch.object(
        customtaskmanager, "RedBeatSchedulerEntry"
    ) as entry_class, patch.object(
        initial, "save_with_first_due"
    ) as exact, patch.object(
        initial, "save"
    ) as ordinary, patch.object(
        initial, "reschedule"
    ) as reschedule:
        entry_class.from_key.side_effect = KeyError
        entry_class.return_value = initial
        customtaskmanager.CustomPeriodicTaskManager().manage_task(
            initial_registration=True, **data
        )
    due, fingerprint = exact.call_args.args
    baseline = NOW + timedelta(
        seconds=interval if kind == "poll" and interval <= 300 else 0
    )
    assert 1 <= (due - baseline).total_seconds() <= 60
    if offset is not None:
        assert due == baseline + timedelta(seconds=offset)
    assert fingerprint.startswith("sha256-v1:60:")
    assert SCHEDULE_CONTEXT not in initial.kwargs
    assert exact.call_args.kwargs["first_run_kwargs"] == (
        {SCHEDULE_CONTEXT: INITIAL_REGISTRATION} if kind == "walk" else {}
    )
    assert initial.options == data["options"]
    assert initial.args == data["args"]
    ordinary.assert_not_called()
    reschedule.assert_not_called()


@pytest.mark.parametrize("enabled,confirmed", [("false", True), ("true", False)])
def test_disabled_or_recovery_creation_stays_legacy(
    app, monkeypatch, enabled, confirmed
):
    monkeypatch.setattr(
        polling_jitter, "JITTER_SETTINGS", JitterSettings(enabled == "true", 60)
    )
    data = definition(app, "walk", 1800)
    initial = RedBeatSchedulerEntry(**data)
    with patch.object(
        customtaskmanager, "RedBeatSchedulerEntry"
    ) as entry_class, patch.object(initial, "save") as save, patch.object(
        initial, "reschedule"
    ) as reschedule, patch.object(
        initial, "save_with_first_due"
    ) as exact:
        entry_class.from_key.side_effect = KeyError
        entry_class.return_value = initial
        customtaskmanager.CustomPeriodicTaskManager().manage_task(
            initial_registration=confirmed, **data
        )
    save.assert_called_once()
    reschedule.assert_called_once()
    exact.assert_not_called()
    assert SCHEDULE_CONTEXT not in initial.kwargs


@pytest.mark.parametrize("interval", [60, 300, 600])
def test_existing_phased_poll_keeps_threshold(app, interval):
    data = definition(app, "poll", interval)
    existing = RedBeatSchedulerEntry(**data)
    existing.jitter_fingerprint = "sha256-v1:60:" + "a" * 64
    with patch.object(
        customtaskmanager.RedBeatSchedulerEntry, "from_key", return_value=existing
    ), patch.object(existing, "update_definition") as update, patch.object(
        existing, "save"
    ) as save, patch.object(
        existing, "save_with_first_due"
    ) as exact:
        customtaskmanager.CustomPeriodicTaskManager().manage_task(
            initial_registration=True, **data
        )
    exact.assert_not_called()
    if interval > 300:
        save.assert_called_once()
        update.assert_not_called()
        assert existing.run_immediately is True
    else:
        update.assert_called_once()
        save.assert_not_called()


def test_operational_walk_request_clears_initial_note(app):
    data = definition(app, "walk", 1800)
    existing = RedBeatSchedulerEntry(**data)
    existing.first_run_kwargs = {SCHEDULE_CONTEXT: INITIAL_REGISTRATION}
    existing.jitter_fingerprint = "sha256-v1:60:" + "a" * 64
    with patch.object(
        customtaskmanager.RedBeatSchedulerEntry, "from_key", return_value=existing
    ), patch.object(existing, "save") as save:
        customtaskmanager.CustomPeriodicTaskManager().manage_task(
            name=data["name"], run_immediately=True
        )
    assert existing.run_immediately is True
    assert SCHEDULE_CONTEXT not in existing.kwargs
    assert existing.first_run_kwargs == {}
    save.assert_called_once()


def test_global_rewalk_preserves_immediate_and_reschedule_calls(app):
    existing = RedBeatSchedulerEntry(**definition(app, "walk", 1800))
    existing.jitter_fingerprint = "sha256-v1:60:" + "a" * 64
    existing.first_run_kwargs = {SCHEDULE_CONTEXT: INITIAL_REGISTRATION}
    with patch.object(
        customtaskmanager, "_get_all_schedules", return_value=[existing]
    ), patch.object(existing, "save") as save, patch.object(
        existing, "reschedule"
    ) as reschedule, patch.object(
        existing, "save_with_first_due"
    ) as exact:
        customtaskmanager.CustomPeriodicTaskManager().rerun_all_walks()
    assert existing.run_immediately is True
    assert SCHEDULE_CONTEXT not in existing.kwargs
    assert existing.first_run_kwargs == {}
    save.assert_called_once()
    reschedule.assert_called_once()
    exact.assert_not_called()


def test_shared_celery_config_does_not_load_polling_jitter():
    """
    Load shared worker configuration without parsing polling-only settings.
    """
    environment = dict(
        os.environ, POLLING_JITTER_ENABLED="false", POLLING_JITTER_WINDOW_SECONDS="0"
    )
    code = """
import sys
import splunk_connect_for_snmp.celery_config

assert "splunk_connect_for_snmp.common.polling_jitter" not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "module",
    [
        "splunk_connect_for_snmp.customtaskmanager",
        "splunk_connect_for_snmp.inventory.loader",
    ],
)
def test_invalid_settings_fail_during_startup_before_storage(module):
    environment = dict(
        os.environ, POLLING_JITTER_ENABLED="false", POLLING_JITTER_WINDOW_SECONDS="0"
    )
    code = """
import importlib
from unittest.mock import patch
with patch("pymongo.MongoClient", side_effect=AssertionError("Unexpected storage access")):
    importlib.import_module(MODULE)
""".replace("MODULE", repr(module))
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode != 0
    assert "POLLING_JITTER_WINDOW_SECONDS" in result.stderr
    assert "ValueError" in result.stderr
    assert "Unexpected storage access" not in result.stderr


@pytest.mark.parametrize("frequency", [True, False, 1.5, 0, -1, None, "bad", 120])
def test_invalid_or_mismatched_poll_frequency_cannot_be_phased(app, frequency):
    data = definition(app, "poll", 60)
    data["kwargs"]["frequency"] = frequency
    initial = RedBeatSchedulerEntry(**data)
    with patch.object(initial, "save_with_first_due") as exact:
        with pytest.raises(ValueError) as error:
            customtaskmanager.CustomPeriodicTaskManager()._save_initial_phase(
                initial, JitterSettings(True)
            )
    assert type(error.value) is PollingJitterError
    exact.assert_not_called()


@pytest.mark.parametrize("interval", [0, -1, 1800.5])
def test_invalid_interval_cannot_be_phased(app, interval):
    initial = RedBeatSchedulerEntry(**definition(app, "walk", interval))
    with patch.object(initial, "save_with_first_due") as exact:
        with pytest.raises(ValueError) as error:
            customtaskmanager.CustomPeriodicTaskManager()._save_initial_phase(
                initial, JitterSettings(True)
            )
    assert type(error.value) is (
        PollingJitterError if interval == 1800.5 else ValueError
    )
    exact.assert_not_called()


@pytest.mark.parametrize(
    "target", ["router-01", "router-01:", ":161", "router-01:bad", "router-01:65536"]
)
def test_invalid_target_cannot_be_phased(app, target):
    data = definition(app, "walk", 1800)
    data["kwargs"]["address"] = target
    initial = RedBeatSchedulerEntry(**data)
    with patch.object(initial, "save_with_first_due") as exact:
        with pytest.raises(ValueError) as error:
            customtaskmanager.CustomPeriodicTaskManager()._save_initial_phase(
                initial, JitterSettings(True)
            )
    expected = PollingJitterError if target in ("router-01", ":161") else ValueError
    assert type(error.value) is expected
    exact.assert_not_called()


def test_phasing_ipv6_keeps_existing_schedule_key(app):
    data = definition(app, "walk", 1800)
    target = "2001:db8::1:161"
    data.update(name=f"sc4snmp;{target};walk", target=target)
    data["kwargs"]["address"] = target
    initial = RedBeatSchedulerEntry(**data)
    with patch.object(initial, "save_with_first_due") as exact:
        customtaskmanager.CustomPeriodicTaskManager()._save_initial_phase(
            initial, JitterSettings(True)
        )
    exact.assert_called_once()
    assert initial.name == f"sc4snmp;{target};walk"


@pytest.mark.parametrize(
    "retained_inventory,retained_walk,expiry,matched",
    [
        (False, False, False, 0),
        (False, True, False, 0),
        (True, False, False, 1),
        (True, True, False, 1),
        (False, False, True, 0),
    ],
)
def test_initial_classification_uses_prior_state(
    app, retained_inventory, retained_walk, expiry, matched
):
    mongo, manager = Mock(), Mock()
    mongo.sc4snmp.inventory.find_one.return_value = (
        {"_id": "retained"} if retained_inventory else None
    )
    mongo.sc4snmp.inventory.update_one.return_value = SimpleNamespace(
        matched_count=matched, modified_count=1, upserted_id=None
    )
    manager.walk_task_exists.return_value = retained_walk
    ir = InventoryRecord(
        address="192.0.2.1",
        port=161,
        walk_interval=1800,
        profiles="A",
        smart_profiles=False,
    )
    order = []
    mongo.sc4snmp.inventory.find_one.side_effect = lambda *a, **k: order.append(
        "read"
    ) or ({"_id": "retained"} if retained_inventory else None)
    mongo.sc4snmp.inventory.update_one.side_effect = lambda *a, **k: order.append(
        "write"
    ) or SimpleNamespace(matched_count=matched, modified_count=1, upserted_id=None)
    InventoryRecordManager(mongo, manager).update(
        ir, {"profiles": "A", "walk_interval": "1800"}, {}, expiry
    )
    should_phase = not retained_inventory and not retained_walk and not expiry
    assert (
        manager.manage_task.call_args.kwargs.get("initial_registration", False)
        is should_phase
    )
    if not expiry:
        assert order == ["read", "write"]


def test_credential_and_profile_changes_are_not_hash_inputs(app):
    from splunk_connect_for_snmp.common.polling_jitter import (
        JitterSettings,
        calculate_offset,
    )

    mongo, manager = Mock(), Mock()
    mongo.sc4snmp.inventory.find_one.return_value = {"_id": "retained"}
    mongo.sc4snmp.inventory.update_one.return_value = SimpleNamespace(
        matched_count=1, modified_count=1, upserted_id=None
    )
    manager.walk_task_exists.return_value = True
    for community in ("test-community-a", "test-community-b"):
        ir = InventoryRecord(
            address="192.0.2.1",
            port=161,
            walk_interval=1800,
            community=community,
            profiles="A;B",
            smart_profiles=False,
        )
        InventoryRecordManager(mongo, manager).update(
            ir, {"profiles": "A;B", "walk_interval": "1800"}, {}, False
        )
        data = manager.manage_task.call_args.kwargs
        assert community not in json.dumps(data["kwargs"])
        assert not data.get("initial_registration")
    assert calculate_offset("router-01", 161, 60, "poll", JitterSettings(True))[0] == 42


@pytest.mark.parametrize(
    "context,enabled,expected",
    [
        (INITIAL_REGISTRATION, "true", True),
        (None, "true", False),
        (INITIAL_REGISTRATION, "false", False),
    ],
)
def test_initial_context_controls_new_poll_setup(
    app, monkeypatch, context, enabled, expected
):
    from splunk_connect_for_snmp.inventory.tasks import inventory_setup_poller

    monkeypatch.setattr(
        polling_jitter, "JITTER_SETTINGS", JitterSettings(enabled == "true", 60)
    )
    manager = Mock()
    with patch(
        "splunk_connect_for_snmp.inventory.tasks.get_mongo_client",
        return_value=MagicMock(),
    ), patch("splunk_connect_for_snmp.inventory.tasks.ProfilesManager"), patch(
        "splunk_connect_for_snmp.inventory.tasks.get_inventory"
    ), patch(
        "splunk_connect_for_snmp.inventory.tasks.assign_profiles",
        return_value=({60: ["A", "B"], 300: ["C"]}, []),
    ), patch.object(
        customtaskmanager, "CustomPeriodicTaskManager", return_value=manager
    ):
        inventory_setup_poller(
            {
                "address": "router-01:161",
                "chain_of_tasks_expiry_time": 120,
                SCHEDULE_CONTEXT: context,
            }
        )
    calls = manager.manage_task.call_args_list
    assert len(calls) == 2
    assert set(calls[0].kwargs["kwargs"]["profiles"]) == {"A", "B"}
    assert calls[0].kwargs.get("initial_registration", False) is expected
    assert calls[1].kwargs.get("initial_registration", False) is expected
    assert SCHEDULE_CONTEXT not in calls[0].kwargs["kwargs"]
    manager.delete_unused_poll_tasks.assert_called_once_with(
        "router-01:161", [call.kwargs["name"] for call in calls]
    )
