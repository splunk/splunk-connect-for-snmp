import time
from copy import deepcopy

import pytest

from integration_tests.tests.jitter.checks import (
    assert_policy_transition,
    assert_preserved,
    expected_policy,
)
from integration_tests.tests.jitter.delivery import (
    assert_indexed_for_all,
    delivery_profiles,
    wait_successful_polls,
)
from integration_tests.utils.polling import short_profiles, wait_for


def transition_observation(live, key, old_fingerprint, new_fingerprint):
    history = [
        (snapshot["finished_at"], snapshot["entries"][key])
        for snapshot in live.observations
        if key in snapshot["entries"]
    ]
    for (_, before), (end, after) in zip(history, history[1:]):
        if (
            before["fingerprint"] == old_fingerprint
            and after["fingerprint"] == new_fingerprint
        ):
            return before, end, after
    return None


def wait_for_poll_policy(live, frequency, window):
    expected = {
        f"{device['label']}/poll/{frequency}": (
            expected_policy(
                device["address"], device["port"], frequency, "poll", window
            )["fingerprint"]
            if window is not None
            else None
        )
        for device in live.devices
    }

    def applied():
        snapshot = live.snapshot()
        if all(
            key in snapshot["entries"]
            and snapshot["entries"][key]["fingerprint"] == fingerprint
            for key, fingerprint in expected.items()
        ):
            return snapshot
        return None

    return wait_for(
        applied, "the requested POLL policy for every simulator", live.timeout
    )


@pytest.mark.part9
@pytest.mark.parametrize(
    "old_enabled,old_window,new_enabled,new_window",
    [
        (False, 60, True, 3),
        (True, 3, True, 8),
        (True, 8, True, 3),
        (True, 3, False, 60),
        (True, 60, True, 120),
    ],
    ids=["enable", "increase", "decrease", "disable", "same-effective-cap"],
)
def test_settings_change_preserves_current_run_and_changes_following_run(
    jitter_live, setup_splunk, old_enabled, old_window, new_enabled, new_window
):
    live = jitter_live

    profiles, rows = short_profiles(), live.inventory()
    profiles["jitter_short"]["frequency"] = 60

    live.configure(profiles, rows, enabled=old_enabled, window=old_window)
    live.wait_entries(len(live.devices) * 2)
    key = "IP1/poll/60"
    baseline = live.wait_count(key, 1)["entries"][key]
    device = next(device for device in live.devices if device["label"] == "IP1")
    fingerprint = (
        expected_policy(device["address"], device["port"], 60, "poll", new_window)[
            "fingerprint"
        ]
        if new_enabled
        else None
    )
    event_start = len(live.events)
    changed_at = time.time()

    live.configure(profiles, rows, enabled=new_enabled, window=new_window)
    live.start_events()
    transition = wait_for(
        lambda: transition_observation(live, key, baseline["fingerprint"], fingerprint),
        "the following-run policy transition",
        live.timeout,
    )
    before, end, after = transition
    assert_policy_transition(before, after, new_enabled, new_window, end)
    # Until reservation, configuration changes must not move accepted work.
    for snapshot in live.observations:
        entry = snapshot["entries"].get(key)
        if entry and entry["count"] == baseline["count"]:
            assert_preserved(baseline, entry)
    wait_for_poll_policy(live, 60, new_window if new_enabled else None)
    wait_successful_polls(live, event_start, frequencies=(60,))
    assert_indexed_for_all(live, setup_splunk, changed_at, kinds=("metrics",))


@pytest.mark.part9
@pytest.mark.parametrize("component", ["scheduler", "worker-poller", "worker-sender"])
def test_component_restart_keeps_identity_and_applied_policy(
    jitter_live, setup_splunk, component
):
    live = jitter_live

    live.configure(short_profiles(), live.inventory(), enabled=True, window=8)
    before = live.wait_entries(len(live.devices) * 2)["entries"]
    event_start = len(live.events)
    restarted_at = time.time()

    live.restart(component)
    live.start_events()
    after = live.wait_entries(len(live.devices) * 2)["entries"]

    assert set(after) == set(before)

    for key in before:
        assert_preserved(before[key], after[key], fields=("entry_id", "fingerprint"))
        if after[key]["count"] == before[key]["count"]:
            assert after[key]["due"] == before[key]["due"]
    wait_successful_polls(live, event_start, frequencies=(10,))
    assert_indexed_for_all(live, setup_splunk, restarted_at, kinds=("metrics",))


@pytest.mark.part9
def test_overlapping_normal_inventory_jobs_preserve_first_registration(
    jitter_live, setup_splunk
):
    live = jitter_live

    started, _ = live.configure(
        short_profiles(), live.inventory(), enabled=True, window=60
    )

    live.load_inventory(concurrent=2)
    live.wait_entries(len(live.devices) * 2)
    first = {}
    for snapshot in live.observations:
        for key, entry in snapshot["entries"].items():
            first.setdefault(key, entry)

    assert (
        len(first) == len(live.devices) * 2
    ), "Initial observation coverage is incomplete"

    for entry in first.values():
        assert entry["fingerprint"], "An initial schedule lost its applied jitter"
        if entry["kind"] == "walk" and entry["count"] == 0:
            assert entry["first_run_kwargs"] == {
                "_schedule_context": "initial_registration"
            }
    # This normal overlap does not guarantee an exact create-write collision.
    # The existing real-Redis regression forces that separate interleaving.
    wait_successful_polls(live, frequencies=(10,))
    assert_indexed_for_all(live, setup_splunk, started, kinds=("metrics",))


@pytest.mark.part9
def test_reenable_after_completed_disable(jitter_live, setup_splunk):
    live = jitter_live

    profiles, rows = short_profiles(), live.inventory()
    profiles["jitter_short"]["frequency"] = 60

    live.configure(profiles, rows, enabled=True, window=3)
    key = "IP1/poll/60"
    live.wait_entries(len(live.devices) * 2)
    initial = live.wait_count(key, 1)["entries"][key]
    event_start = len(live.events)
    disabled_at = time.time()

    live.configure(profiles, rows, enabled=False)
    live.start_events()
    disabled = wait_for(
        lambda: transition_observation(live, key, initial["fingerprint"], None),
        "completed disable before re-enable",
        live.timeout,
    )
    before, end, after = disabled
    assert_policy_transition(before, after, False, 60, end)
    wait_for_poll_policy(live, 60, None)
    wait_successful_polls(live, event_start, frequencies=(60,))
    assert_indexed_for_all(live, setup_splunk, disabled_at, kinds=("metrics",))
    event_start = len(live.events)
    enabled_at = time.time()

    live.configure(profiles, rows, enabled=True, window=8)
    live.start_events()
    device = next(device for device in live.devices if device["label"] == "IP1")
    fingerprint = expected_policy(device["address"], device["port"], 60, "poll", 8)[
        "fingerprint"
    ]
    enabled = wait_for(
        lambda: transition_observation(live, key, None, fingerprint),
        "following-run re-enable",
        live.timeout,
    )
    before, end, after = enabled
    assert_policy_transition(before, after, True, 8, end)

    assert after["entry_id"] == initial["entry_id"]
    wait_for_poll_policy(live, 60, 8)
    wait_successful_polls(live, event_start, frequencies=(60,))
    assert_indexed_for_all(live, setup_splunk, enabled_at, kinds=("metrics",))


@pytest.mark.part11
@pytest.mark.long_interval
def test_beat_restart_continues_partial_policy_adoption(jitter_live, setup_splunk):
    live = jitter_live

    profiles = {
        **delivery_profiles(),
        "jitter_later": {
            "frequency": 300,
            "varBinds": [["SNMPv2-MIB", "sysUpTime", 0]],
        },
    }
    rows = live.inventory("jitter_short;jitter_events;jitter_later")

    live.configure(profiles, rows, enabled=True, window=3)
    original = live.wait_entries(len(live.devices) * 4)["entries"]
    wait_successful_polls(live)

    live.configure(profiles, rows, enabled=True, window=8)
    live.start_events()
    wait_for_poll_policy(live, 10, 8)
    mixed = live.snapshot()["entries"]

    for device in live.devices:
        key = f"{device['label']}/poll/300"
        assert_preserved(original[key], mixed[key])
        assert mixed[key]["due"] > time.time() + 60, (
            "Coverage gap: the long POLL is too near its first due to observe "
            "a restart during partial policy adoption"
        )
    event_start = len(live.events)
    restarted_at = time.time()

    live.restart("scheduler")
    live.start_events()
    retained = live.snapshot()["entries"]
    for device in live.devices:
        key = f"{device['label']}/poll/300"
        assert_preserved(mixed[key], retained[key])
        short_key = f"{device['label']}/poll/10"
        assert_preserved(
            mixed[short_key], retained[short_key], ("entry_id", "fingerprint")
        )
    adopted = wait_for_poll_policy(live, 300, 8)["entries"]

    for key, entry in original.items():
        assert adopted[key]["entry_id"] == entry["entry_id"]
    wait_successful_polls(live, event_start, frequencies=(300,))
    assert_indexed_for_all(live, setup_splunk, restarted_at)


@pytest.mark.part11
@pytest.mark.long_interval
def test_later_walk_refresh_runs_existing_long_poll_before_initial_deadline(
    jitter_live, setup_splunk
):
    live = jitter_live

    profiles = {
        "jitter_long": {
            "frequency": 301,
            "varBinds": [["SNMPv2-MIB", "sysUpTime", 0]],
        }
    }
    rows = live.inventory("jitter_long")

    candidates = []
    for window in range(61, 301):
        for device in live.devices:
            poll_offset = expected_policy(
                device["address"], device["port"], 301, "poll", window
            )["offset"]
            walk_offset = expected_policy(
                device["address"], device["port"], 1800, "walk", window
            )["offset"]
            candidates.append((poll_offset - walk_offset, window))
    slack, window = max(candidates)
    assert slack > 90, "Simulator identities must allow a real initial-run overlap"
    live.configure(profiles, rows, enabled=True, window=window)
    offsets = {
        device["label"]: expected_policy(
            device["address"], device["port"], 1800, "walk", window
        )["offset"]
        for device in live.devices
    }

    def eligible_initial_poll():
        entries = live.snapshot()["entries"]
        candidates = []
        for device in live.devices:
            key = f"{device['label']}/poll/301"
            poll = entries.get(key)
            if not poll or poll["count"]:
                continue
            slack = poll["due"] - time.time() - offsets[device["label"]]
            if slack > 60:
                candidates.append((slack, device, key, poll))
        if candidates:
            return max(candidates, key=lambda candidate: candidate[0])
        return None

    # Select early. Waiting for the fleet's latest WALK can consume the very
    # initial POLL delay that this overlap needs to observe.
    candidate = wait_for(
        eligible_initial_poll,
        "a pending initial POLL with time for its inventory refresh",
        live.timeout,
    )
    _, device, key, before = candidate
    profiles["jitter_long_updated"] = deepcopy(profiles["jitter_long"])
    updated = [
        (
            {**row, "profiles": "jitter_long;jitter_long_updated"}
            if row["address"] == device["address"]
            else row
        )
        for row in rows
    ]
    event_start = len(live.events)
    refreshed_at = time.time()

    live.configure(profiles, updated, enabled=True, window=window)
    completed = wait_for(
        lambda: [
            event
            for event in live.events[event_start:]
            if event["label"] == device["label"]
            and event["kind"] == "poll"
            and event["state"] == "task-succeeded"
        ],
        "urgent long-POLL completion before its original first due",
        live.timeout,
    )

    assert completed[0]["timestamp"] < before["due"]
    current = live.snapshot()["entries"][key]

    assert current["entry_id"] == before["entry_id"]
    assert set(current["profiles"]) == {"jitter_long", "jitter_long_updated"}
    assert_indexed_for_all(
        live,
        setup_splunk,
        refreshed_at,
        kinds=("metrics",),
        labels={device["label"]},
    )


@pytest.mark.part11
@pytest.mark.long_interval
def test_delayed_inventory_request_survives_disable(jitter_live, setup_splunk):
    live = jitter_live

    profiles, rows = short_profiles(), live.inventory()

    live.configure(profiles, rows, enabled=True, window=120)
    live.wait_entries(len(live.devices) * 2)
    profiles = {**profiles, "jitter_updated": deepcopy(profiles["jitter_short"])}
    updated_rows = [{**row, "profiles": "jitter_updated"} for row in rows]

    live.configure(profiles, updated_rows, enabled=True, window=120)
    waiting = live.snapshot()["entries"]
    candidates = {
        key: entry
        for key, entry in waiting.items()
        if entry["kind"] == "walk" and entry["immediate"]
    }

    assert candidates, "No delayed inventory request was captured while pending"
    key, before = max(candidates.items(), key=lambda item: item[1]["due"])
    event_start = len(live.events)
    disabled_at = time.time()

    live.configure(profiles, updated_rows, enabled=False)
    live.start_events()
    current = live.snapshot()["entries"][key]

    assert (
        current["count"] == before["count"]
    ), "The request ran before disabled settings became active. Repeat with adequate observation time"
    assert_preserved(before, current)
    live.wait_count(key, before["count"] + 1)
    transition = wait_for(
        lambda: transition_observation(live, key, before["fingerprint"], None),
        "request consumption and following disable alignment",
        live.timeout,
    )
    previous, end, after = transition
    assert_policy_transition(previous, after, False, 60, end)
    poll_key = f"{key.split('/')[0]}/poll/10"
    wait_for(
        lambda: live.snapshot()["entries"][poll_key]["profiles"] == ["jitter_updated"],
        "the accepted WALK's updated profile assignment",
        live.timeout,
    )
    wait_successful_polls(live, event_start, frequencies=(10,))
    assert_indexed_for_all(live, setup_splunk, disabled_at, kinds=("metrics",))
