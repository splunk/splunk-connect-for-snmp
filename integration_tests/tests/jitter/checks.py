import hashlib
import ipaddress
import math
from datetime import datetime, timedelta, timezone


def expected_policy(address, port, interval, kind, window):
    assert interval > 1 and interval == int(interval)
    interval = int(interval)
    address = address.strip()
    try:
        address = str(ipaddress.ip_address(address))
    except ValueError:
        address = address.casefold()
    assert kind in ("walk", "poll")
    effective_window = min(window, interval - 1)
    identity = f"v1|{kind}|{address}|{int(port)}|{interval}"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return {
        "offset": 1 + int(digest, 16) % effective_window,
        "fingerprint": f"sha256-v1:{window}:{digest}",
        "effective_window": effective_window,
    }


def next_disabled_due(reserved_at, interval):
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    duration = timedelta(seconds=interval)
    baseline = datetime.fromtimestamp(reserved_at, tz=timezone.utc) + duration
    quotient, remainder = divmod(baseline - epoch, duration)
    if remainder * 2 >= duration:
        quotient += 1
    return (epoch + quotient * duration).timestamp()


def assert_entry_policy(entry, device, window):
    schedule = f"{entry.get('label', 'device')}/{entry['kind']}/{entry['interval']}"
    expected = expected_policy(
        device["address"], device["port"], entry["interval"], entry["kind"], window
    )
    assert entry["fingerprint"] == expected["fingerprint"], f"{schedule}: fingerprint"
    assert entry["entry_id"], f"{schedule}: entry_id"
    assert math.isclose(
        entry["due"],
        entry["last_run_at"] + entry["interval"],
        rel_tol=0,
        abs_tol=0.000001,
    ), f"{schedule}: due differs from the stored interval anchor"
    if entry["count"] == 0 and not entry["immediate"]:
        assert entry["score"] == int(entry["due"]), f"{schedule}: initial score"


def assert_preserved(before, after, fields=("due", "entry_id", "count", "fingerprint")):
    for field in fields:
        assert after[field] == before[field], f"Stored {field} changed"


def assert_policy_transition(
    before, after, requested_enabled, window, reservation_finished_at
):
    schedule = f"{after.get('label', 'device')}/{after['kind']}/{after['interval']}"
    assert after["entry_id"] == before["entry_id"], f"{schedule}: entry_id changed"
    assert after["interval"] == before["interval"], f"{schedule}: interval changed"
    assert after["count"] == before["count"] + 1, f"{schedule}: reservation count"
    # Beat may choose its run time before an observer reads the old state.
    # The saved due is the earliest it can reserve that run.
    start, end = before["due"], reservation_finished_at
    assert start <= end
    interval = after["interval"]
    previous = before["fingerprint"]
    if requested_enabled:
        algorithm, configured_window, digest = after["fingerprint"].split(":")
        assert algorithm == "sha256-v1"
        assert int(configured_window) == window
        effective_window = min(window, interval - 1)
        previous_window = int(previous.split(":")[1]) if previous else None
        same_range = previous_window is not None and (
            min(previous_window, interval - 1) == effective_window
        )
        offset = 0 if same_range else 1 + int(digest, 16) % effective_window
        earliest = start + interval + offset
        latest = end + interval + offset
    else:
        assert after["fingerprint"] is None, f"{schedule}: disabled fingerprint"
        if previous:
            earliest = next_disabled_due(start, interval)
            latest = next_disabled_due(end, interval)
        else:
            earliest, latest = start + interval, end + interval
    assert (
        earliest - 0.000001 <= after["due"] <= latest + 0.000001
    ), f"{schedule}: following due is outside its observed reservation bounds"
