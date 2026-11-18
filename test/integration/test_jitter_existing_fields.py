from datetime import timedelta
from unittest.mock import patch

from redbeat.schedulers import RedBeatScheduler, RedBeatSchedulerEntry
from test_polling_jitter_integration import NOW

from splunk_connect_for_snmp import customtaskmanager
from splunk_connect_for_snmp.common import polling_jitter
from splunk_connect_for_snmp.common.polling_jitter import (
    JitterSettings,
    calculate_offset,
    first_due,
)
from splunk_connect_for_snmp.common.task_generator import WalkTaskGenerator
from splunk_connect_for_snmp.jitter_reconcile import apply_entry_policy


def test_500_device_refreshes_reload_and_preserve_their_deadlines(app, monkeypatch):
    monkeypatch.setattr(customtaskmanager, "app", app)
    settings = JitterSettings(True, 60)
    monkeypatch.setattr(polling_jitter, "JITTER_SETTINGS", settings)
    app.conf.redbeat_entry_policy = apply_entry_policy
    app.now = lambda: NOW
    manager = customtaskmanager.CustomPeriodicTaskManager()
    definitions = []
    expected = {}
    for index in range(500):
        address = f"agent-{index:04d}"
        data = WalkTaskGenerator(
            f"{address}:161", 1800, app, None, "Walk"
        ).generate_task_definition()
        manager.manage_task(initial_registration=True, **data)
        definitions.append(data)
        offset, _ = calculate_offset(address, 161, 1800, "walk", settings)
        expected[data["kwargs"]["address"]] = first_due(NOW, offset)

    scheduler = RedBeatScheduler(app, lazy=True, max_interval=3600)
    try:
        with patch.object(app, "send_task") as publish:
            for second in range(61):
                app.now = lambda: NOW + timedelta(seconds=second)
                scheduler.tick()
            assert publish.call_count == 500
        request_time = NOW + timedelta(minutes=2)
        for data in definitions:
            app.now = lambda: request_time
            data["kwargs"]["profile"] = "FirstEdit"
            manager.manage_task(inventory_update=True, **data)
            app.now = lambda: request_time + timedelta(microseconds=250000)
            data["kwargs"]["profile"] = "LatestEdit"
            manager.manage_task(inventory_update=True, **data)
            key = "redbeat:" + data["name"]
            entry = RedBeatSchedulerEntry.from_key(key, app=app)
            expected[entry.kwargs["address"]] += timedelta(minutes=2)
            assert (
                entry.last_run_at + entry.schedule.run_every
                == expected[entry.kwargs["address"]]
            )
            assert entry.total_run_count == 1
            assert set(app.redbeat_redis.hkeys(key)) == {
                "definition",
                "meta",
                "jitter_fingerprint",
                "entry_id",
            }
            assert entry.entry_id
            assert "entry_id" not in RedBeatSchedulerEntry.load_definition(key, app=app)

        # A replacement scheduler must reload the same deadlines and latest payloads.
        scheduler.close()
        scheduler = RedBeatScheduler(app, lazy=True, max_interval=3600)
        with patch.object(app, "send_task") as publish:
            for second in range(61):
                tick_time = request_time + timedelta(seconds=second)
                if second == 0:
                    tick_time += timedelta(microseconds=250000)
                app.now = lambda: tick_time
                before = publish.call_count
                scheduler.tick()
                for call in publish.call_args_list[before:]:
                    kwargs = call.args[2]
                    assert expected[kwargs["address"]] == app.now()
                    assert kwargs["profile"] == "LatestEdit"
                    assert "_schedule_context" not in kwargs
            assert publish.call_count == 500
        for data in definitions:
            key = "redbeat:" + data["name"]
            entry = RedBeatSchedulerEntry.from_key(key, app=app)
            due = expected[entry.kwargs["address"]]
            assert entry.last_run_at == due
            assert entry.total_run_count == 2
            assert not entry._strtobool(entry.run_immediately)
            assert (
                app.redbeat_redis.zscore(app.redbeat_conf.schedule_key, key)
                == (due + timedelta(seconds=1800)).timestamp()
            )
    finally:
        scheduler.close()
