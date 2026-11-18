import time
from copy import deepcopy

import pytest

from integration_tests.tests.jitter.checks import assert_entry_policy
from integration_tests.tests.jitter.delivery import (
    assert_indexed_for_all,
    wait_successful_polls,
)
from integration_tests.utils.polling import short_profiles, wait_for

pytestmark = pytest.mark.part16


@pytest.mark.parametrize("missing", ["walk", "poll", "both"])
@pytest.mark.parametrize("enabled", [False, True])
def test_owned_schedule_loss_recovers_through_inventory_and_walk(
    jitter_live, setup_splunk, missing, enabled
):
    live = jitter_live

    profiles, rows = short_profiles(), live.inventory()

    live.configure(profiles, rows, enabled=enabled, window=8)
    before = live.wait_entries(len(live.devices) * 2)["entries"]
    live.wait_count("IP1/poll/10", 1)
    selected = [
        key
        for key in before
        if key.startswith("IP1/") and (missing == "both" or f"/{missing}/" in key)
    ]

    assert len(selected) == (2 if missing == "both" else 1)
    event_start = len(live.events)

    assert live.probe("remove_schedules", selected=selected)["removed"] == len(selected)
    removed_at = time.time()
    observation_start = len(live.observations)

    if missing == "poll":
        live.load_inventory()
        assert (
            "IP1/poll/10" not in live.snapshot()["entries"]
        ), "Unchanged inventory unexpectedly repaired a missing-only-POLL schedule"
        # A real assignment edit requests a normal WALK, which owns POLL recovery.
        profiles["jitter_recovery"] = deepcopy(profiles["jitter_short"])
        rows = [
            {**row, "profiles": "jitter_recovery"} if index == 0 else row
            for index, row in enumerate(rows)
        ]
        live.configure(profiles, rows, enabled=enabled, window=8)
    else:
        live.load_inventory()
    recovered = live.wait_entries(len(live.devices) * 2)["entries"]

    for key in before:
        if key in selected:
            assert recovered[key]["entry_id"] != before[key]["entry_id"]
        else:
            assert recovered[key]["entry_id"] == before[key]["entry_id"]

    if missing != "walk":
        captures = [
            snapshot["entries"]["IP1/poll/10"]
            for snapshot in live.observations[observation_start:]
            if "IP1/poll/10" in snapshot["entries"]
            and snapshot["entries"]["IP1/poll/10"]["entry_id"]
            != before["IP1/poll/10"]["entry_id"]
        ]
        assert captures, "The recreated POLL was not observed"
        assert captures[0]["count"] == 0, "Initial recovery timing was not captured"
        assert captures[0]["fingerprint"] is None
        assert not captures[0]["first_run_kwargs"]
        wait_successful_polls(live, event_start, frequencies=(10,), labels={"IP1"})

    expected_kinds = {key.split("/")[1] for key in selected}

    def completed_recovery_tasks():
        received = {
            event["uuid"]: event["kind"]
            for event in live.events[event_start:]
            if event["label"] == "IP1"
            and event["state"] == "task-received"
            and event["timestamp"] >= removed_at
            and event["kind"] in expected_kinds
        }
        succeeded = {
            received[event["uuid"]]
            for event in live.events[event_start:]
            if event["state"] == "task-succeeded" and event["uuid"] in received
        }
        return succeeded >= expected_kinds

    wait_for(
        completed_recovery_tasks,
        "successful newly received recovery tasks for the selected simulator",
        live.timeout,
    )

    if missing != "poll":
        recovered_walk = live.wait_count("IP1/walk/1800", 1)["entries"]["IP1/walk/1800"]
        walk_captures = [
            snapshot["entries"]["IP1/walk/1800"]
            for snapshot in live.observations[observation_start:]
            if "IP1/walk/1800" in snapshot["entries"]
            and snapshot["entries"]["IP1/walk/1800"]["entry_id"]
            != before["IP1/walk/1800"]["entry_id"]
        ]
        initial_walk = next(
            (entry for entry in walk_captures if entry["count"] == 0), None
        )
        if initial_walk:
            assert initial_walk["fingerprint"] is None
            assert not initial_walk["first_run_kwargs"]
            assert initial_walk["immediate"]
        device = next(device for device in live.devices if device["label"] == "IP1")
        if enabled:
            # The recovery WALK ran without an initial offset. Its reservation
            # applies enabled jitter only to the following 30-minute due time.
            assert_entry_policy(recovered_walk, device, 8)
        else:
            assert recovered_walk["fingerprint"] is None
    if enabled:

        def adopted():
            entry = live.snapshot()["entries"].get("IP1/poll/10")
            return entry if entry and entry["fingerprint"] and entry["count"] else None

        entry = wait_for(
            adopted, "ordinary policy adoption after recovery", live.timeout
        )
        device = next(device for device in live.devices if device["label"] == "IP1")
        assert_entry_policy(entry, device, 8)
    assert_indexed_for_all(live, setup_splunk, removed_at, kinds=("metrics",))
