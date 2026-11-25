import json
import math
import re

from splunklib.results import JSONResultsReader

from integration_tests.utils.polling import short_profiles, wait_for


def delivery_profiles():
    return {
        **short_profiles(),
        "jitter_events": {
            "frequency": 20,
            "varBinds": [["SNMPv2-MIB", "sysDescr", 0]],
        },
    }


def wait_indexed(live, service, search, devices, description):
    expected = {
        f"{device['address']}:{device['port']}": device["label"] for device in devices
    }

    def indexed():
        stream = service.jobs.oneshot(search, output_mode="json")
        try:
            counts = {
                row["host"]: float(row.get("count") or 0)
                for row in JSONResultsReader(stream)
                if isinstance(row, dict) and "host" in row
            }
        finally:
            stream.close()
        if all(counts.get(host, 0) > 0 for host in expected):
            return {label: counts[host] for host, label in expected.items()}
        return None

    return wait_for(indexed, description, live.timeout, interval=2)


def search_scope(live, started, kind, labels=None):
    devices = [
        device for device in live.devices if labels is None or device["label"] in labels
    ]
    assert devices, "At least one expected simulator is required for ingestion"
    index = live.target.get(
        "event_index" if kind == "events" else "metric_index",
        "netops" if kind == "events" else "netmetrics",
    )
    assert re.fullmatch(r"[A-Za-z0-9_-]+", index)
    hosts = " OR ".join(
        f"host={json.dumps(device['address'] + ':' + str(device['port']))}"
        for device in devices
    )
    # Exclude earlier output from the same second as registration or promotion.
    return devices, f"index={index} ({hosts}) earliest={math.ceil(started)}"


def assert_indexed_for_all(
    live, service, started, *, kinds=("events", "metrics"), labels=None
):
    for kind in kinds:
        devices, scope = search_scope(live, started, kind, labels)
        if kind == "events":
            search = f"search {scope} sourcetype=sc4snmp:event | stats count by host"
        else:
            search = f"| mstats count(_value) AS count WHERE {scope} metric_name=sc4snmp.* BY host"
        wait_indexed(
            live,
            service,
            search,
            devices,
            f"fresh indexed {kind} for every expected simulator",
        )


def assert_indexed_field(live, service, started, field, expected):
    assert re.fullmatch(r"[A-Za-z0-9_.-]+", field)
    metric = field.startswith("sc4snmp.")
    devices, scope = search_scope(live, started, "metrics" if metric else "events")
    if metric:
        assert expected is None, "Metric assertions here check presence, not a value"
        search = f"| mstats count(_value) AS count WHERE {scope} metric_name={json.dumps(field)} BY host"
    else:
        search = f"search {scope} sourcetype=sc4snmp:event | where '{field}'={json.dumps(expected)} | stats count by host"
    return wait_indexed(
        live,
        service,
        search,
        devices,
        f"indexed field {field} for every expected simulator",
    )


def wait_successful_polls(live, event_start=0, frequencies=(10, 20), labels=None):
    return wait_for(
        lambda: {
            (event["label"], event.get("frequency"))
            for event in live.events[event_start:]
            if event["kind"] == "poll" and event["state"] == "task-succeeded"
        }
        >= {
            (device["label"], frequency)
            for device in live.devices
            if labels is None or device["label"] in labels
            for frequency in frequencies
        },
        "successful POLL completion for every simulator",
        live.timeout,
    )
