import math

import pytest

from integration_tests.tests.jitter.checks import assert_entry_policy, expected_policy
from integration_tests.tests.jitter.delivery import (
    assert_indexed_for_all,
    delivery_profiles,
    wait_successful_polls,
)
from integration_tests.utils.polling import short_profiles, wait_for


def first_observations(live, expected):
    wait_for(
        lambda: any(
            len(snapshot["entries"]) == expected for snapshot in live.observations
        ),
        "complete initial schedule observations",
        live.timeout,
    )
    first = {}
    for snapshot in live.observations:
        for key, entry in snapshot["entries"].items():
            first.setdefault(key, (snapshot["finished_at"], entry))
    assert len(first) == expected, "Not every initial deadline was captured"
    assert all(
        entry["count"] == 0 for _, entry in first.values()
    ), "A first reservation was observed without its initial deadline"
    return first


@pytest.mark.part9
@pytest.mark.parametrize("enabled", [False, True])
def test_registration_grouping_and_first_deadlines(jitter_live, enabled):
    live = jitter_live

    profiles = short_profiles()
    profiles["jitter_same_frequency"] = {
        "frequency": 10,
        "varBinds": [["SNMPv2-MIB", "sysDescr", 0]],
    }
    rows = live.inventory("jitter_short;jitter_same_frequency")

    started, _ = live.configure(profiles, rows, enabled=enabled, window=20)
    live.wait_entries(len(live.devices) * 2)

    if not enabled:
        entries = list(live.snapshot()["entries"].values())
        assert all(entry["fingerprint"] is None for entry in entries)
        assert all(not entry["first_run_kwargs"] for entry in entries)
        polls = [entry for entry in entries if entry["kind"] == "poll"]
        assert len(polls) == len(live.devices)
        assert all(
            set(entry["profiles"]) == {"jitter_short", "jitter_same_frequency"}
            for entry in polls
        )
        return
    captured = first_observations(live, len(live.devices) * 2)
    by_label = {device["label"]: device for device in live.devices}

    for observed_at, entry in captured.values():
        assert_entry_policy(entry, by_label[entry["label"]], 20)
        offset = expected_policy(
            by_label[entry["label"]]["address"],
            by_label[entry["label"]]["port"],
            int(entry["interval"]),
            entry["kind"],
            20,
        )["offset"]
        baseline = entry["due"] - offset
        if entry["kind"] == "poll":
            baseline -= entry["interval"]
        assert started <= baseline <= observed_at
        if entry["kind"] == "walk":
            assert entry["first_run_kwargs"] == {
                "_schedule_context": "initial_registration"
            }
        if entry["kind"] == "poll":
            assert set(entry["profiles"]) == {"jitter_short", "jitter_same_frequency"}


@pytest.mark.part9
def test_ordinary_recurrence_does_not_add_the_offset_again(jitter_live, setup_splunk):
    live = jitter_live

    started, _ = live.configure(
        short_profiles(), live.inventory(), enabled=True, window=8
    )
    live.wait_entries(len(live.devices) * 2)
    live.wait_count("IP1/poll/10", 3)
    observations = [
        (
            snapshot["finished_at"],
            snapshot["entries"]["IP1/poll/10"],
        )
        for snapshot in live.observations
        if "IP1/poll/10" in snapshot["entries"]
    ]
    checked = 0

    for (_, before), (new_time, after) in zip(observations, observations[1:]):
        if after["count"] == before["count"] + 1:
            assert after["fingerprint"] == before["fingerprint"]
            assert after["entry_id"] == before["entry_id"]
            reserved_at = after["last_run_at"]
            # Beat can choose its run time before the previous Redis read,
            # then save that reservation while the observer is reading.
            assert before["last_run_at"] <= reserved_at <= new_time
            assert reserved_at >= before["due"]
            assert math.isclose(after["due"] - reserved_at, 10, abs_tol=0.000001)
            checked += 1

    assert checked >= 2, "Insufficient consecutive reservation evidence"
    wait_successful_polls(live, frequencies=(10,))
    assert_indexed_for_all(live, setup_splunk, started, kinds=("metrics",))


@pytest.mark.part11
@pytest.mark.long_interval
def test_initial_300_and_301_second_boundary(jitter_live, setup_splunk):
    live = jitter_live

    profiles = {
        f"jitter_{frequency}": {
            "frequency": frequency,
            "varBinds": [["SNMPv2-MIB", "sysUpTime", 0]],
        }
        for frequency in (300, 301)
    }

    started, _ = live.configure(
        profiles, live.inventory("jitter_300;jitter_301"), enabled=True, window=20
    )
    live.wait_entries(len(live.devices) * 3)
    captured = first_observations(live, len(live.devices) * 3)
    devices = {device["label"]: device for device in live.devices}

    for observed, entry in captured.values():
        assert_entry_policy(entry, devices[entry["label"]], 20)
        device = devices[entry["label"]]
        offset = expected_policy(
            device["address"], device["port"], int(entry["interval"]), entry["kind"], 20
        )["offset"]
        baseline = entry["due"] - offset
        if entry["kind"] == "poll" and entry["interval"] == 300:
            baseline -= 300
        assert started <= baseline <= observed
    live.wait_count("IP1/poll/300", 1)
    live.wait_count("IP1/poll/301", 1)
    wait_successful_polls(live, frequencies=(300, 301))
    assert_indexed_for_all(live, setup_splunk, started, kinds=("metrics",))


@pytest.mark.part9
def test_events_and_metrics_are_indexed_for_every_simulator(jitter_live, setup_splunk):
    live = jitter_live

    started, _ = live.configure(
        delivery_profiles(),
        live.inventory("jitter_short;jitter_events"),
        enabled=True,
        window=8,
    )
    live.wait_entries(len(live.devices) * 3)
    wait_successful_polls(live)
    assert_indexed_for_all(live, setup_splunk, started)
