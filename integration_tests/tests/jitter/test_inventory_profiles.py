import pytest

from integration_tests.tests.jitter.checks import assert_entry_policy, assert_preserved
from integration_tests.tests.jitter.delivery import (
    assert_indexed_field,
    assert_indexed_for_all,
    delivery_profiles,
    wait_successful_polls,
)
from integration_tests.utils.polling import short_profiles, wait_for


def wait_for_layout(live, poll_profiles, walk_interval=1800, labels=None):
    devices = [
        device for device in live.devices if labels is None or device["label"] in labels
    ]
    expected = {
        f"{device['label']}/{kind}/{interval}"
        for device in devices
        for kind, interval in [("walk", walk_interval)]
        + [("poll", frequency) for frequency in poll_profiles]
    }

    def reconciled():
        snapshot = live.snapshot()
        entries = snapshot["entries"]
        if set(entries) != expected:
            return None
        for device in devices:
            for frequency, profiles in poll_profiles.items():
                entry = entries[f"{device['label']}/poll/{frequency}"]
                if set(entry["profiles"]) != profiles:
                    return None
        return snapshot

    return wait_for(reconciled, "the requested device-frequency profiles", live.timeout)


def assert_existing_schedules(before, after):
    assert set(before["entries"]) == set(after["entries"])
    for key, entry in before["entries"].items():
        current = after["entries"][key]
        assert_preserved(entry, current, ("entry_id", "fingerprint"))
        assert current["count"] >= entry["count"]
        if current["count"] == entry["count"]:
            assert_preserved(entry, current, ("due",))


@pytest.mark.part14
@pytest.mark.parametrize("enabled", [False, True])
def test_unchanged_csv_reload_keeps_existing_schedules(
    jitter_live, setup_splunk, enabled
):
    live = jitter_live

    profiles = delivery_profiles()
    rows = live.inventory("jitter_short;jitter_events")

    started, _ = live.configure(profiles, rows, enabled=enabled, window=8)
    wait_for_layout(live, {10: {"jitter_short"}, 20: {"jitter_events"}})
    wait_successful_polls(live)
    assert_indexed_for_all(live, setup_splunk, started)
    before = live.snapshot()

    live.load_inventory()
    after = live.snapshot()
    assert_existing_schedules(before, after)
    for key, entry in before["entries"].items():
        if entry["kind"] == "walk":
            # An unchanged inventory does not request another 30-minute WALK.
            assert_preserved(entry, after["entries"][key])


@pytest.mark.part14
@pytest.mark.parametrize("enabled", [False, True])
def test_varbind_only_profile_edit_reaches_splunk_without_rephasing(
    jitter_live, setup_splunk, enabled
):
    live = jitter_live

    profiles = delivery_profiles()
    rows = live.inventory("jitter_short;jitter_events")

    started, _ = live.configure(profiles, rows, enabled=enabled, window=8)
    wait_for_layout(live, {10: {"jitter_short"}, 20: {"jitter_events"}})
    wait_successful_polls(live)
    assert_indexed_for_all(live, setup_splunk, started)
    before = live.snapshot()

    profiles["jitter_events"]["varBinds"] = [["SNMPv2-MIB", "sysLocation", 0]]

    edited_at, _ = live.configure(profiles, rows, enabled=enabled, window=8)
    after = wait_for_layout(live, {10: {"jitter_short"}, 20: {"jitter_events"}})
    assert_existing_schedules(before, after)
    for key, entry in before["entries"].items():
        if entry["kind"] == "walk":
            assert_preserved(entry, after["entries"][key])
    # Only the recurring string-only POLL can produce this newly selected field.
    assert_indexed_field(
        live,
        setup_splunk,
        edited_at,
        "SNMPv2-MIB.sysLocation.value",
        "integration-lab",
    )


@pytest.mark.part14
@pytest.mark.parametrize("enabled", [False, True])
def test_snmpv2c_to_v1_inventory_change_keeps_device_phase(
    jitter_live, setup_splunk, enabled
):
    live = jitter_live

    profiles = delivery_profiles()
    rows = live.inventory("jitter_short;jitter_events")

    live.configure(profiles, rows, enabled=enabled, window=8)
    before = wait_for_layout(live, {10: {"jitter_short"}, 20: {"jitter_events"}})
    wait_successful_polls(live)

    changed = [dict(row) for row in rows]
    for row in changed:
        if row["version"] == "2c":
            row["version"] = "1"
    event_start = len(live.events)

    started, _ = live.configure(profiles, changed, enabled=enabled, window=8)
    after = wait_for_layout(live, {10: {"jitter_short"}, 20: {"jitter_events"}})
    for key, entry in before["entries"].items():
        assert_preserved(entry, after["entries"][key], ("entry_id", "fingerprint"))
    wait_successful_polls(live, event_start)
    assert_indexed_for_all(live, setup_splunk, started)


@pytest.mark.part10
@pytest.mark.parametrize("enabled", [False, True])
def test_group_overrides_member_removal_and_group_deletion(
    jitter_live, setup_splunk, enabled
):
    live = jitter_live

    profiles = delivery_profiles()
    direct_rows = live.inventory("jitter_short;jitter_events")
    override_fields = (
        "address",
        "port",
        "version",
        "community",
        "secret",
        "security_engine",
    )
    members = [{field: row[field] for field in override_fields} for row in direct_rows]
    group_row = dict(direct_rows[0], address="jitter_devices")

    started, _ = live.configure(
        profiles,
        [group_row],
        groups={"jitter_devices": members},
        enabled=enabled,
        window=8,
    )
    before = wait_for_layout(live, {10: {"jitter_short"}, 20: {"jitter_events"}})

    assert all(
        entry["group"] == "jitter_devices" for entry in before["entries"].values()
    )
    wait_successful_polls(live)
    assert_indexed_for_all(live, setup_splunk, started)

    live.configure(
        profiles,
        [group_row],
        groups={"jitter_devices": members[1:]},
        enabled=enabled,
        window=8,
    )
    remaining = {device["label"] for device in live.devices[1:]}
    after = wait_for_layout(
        live, {10: {"jitter_short"}, 20: {"jitter_events"}}, labels=remaining
    )
    for key, entry in after["entries"].items():
        assert_preserved(before["entries"][key], entry, ("entry_id", "fingerprint"))

    # Remove the parent row too so the deleted group is not treated as a hostname.

    live.configure(profiles, [], groups={}, enabled=enabled, window=8)
    wait_for_layout(live, {}, labels=set())


@pytest.mark.part14
@pytest.mark.mongo_inventory
@pytest.mark.parametrize("enabled", [False, True])
def test_csv_mongo_source_switch_and_native_inventory_lifecycle(
    jitter_live, setup_splunk, enabled
):
    live = jitter_live

    profiles = delivery_profiles()
    rows = live.inventory("jitter_short;jitter_events")
    layout = {10: {"jitter_short"}, 20: {"jitter_events"}}

    started, _ = live.configure(profiles, rows, enabled=enabled, window=8)
    wait_for_layout(live, layout)
    wait_successful_polls(live)
    assert_indexed_for_all(live, setup_splunk, started)
    before = live.snapshot()

    live.configure(profiles, rows, enabled=enabled, window=8, from_mongo=True)
    seeded = wait_for_layout(live, layout)
    assert_existing_schedules(before, seeded)
    for key, entry in before["entries"].items():
        if entry["kind"] == "walk":
            assert_preserved(entry, seeded["entries"][key])

    profiles["jitter_mongo_extra"] = {
        "frequency": 10,
        "varBinds": [["SNMPv2-MIB", "sysLocation", 0]],
    }
    rows = live.inventory("jitter_short;jitter_events;jitter_mongo_extra")
    layout = {10: {"jitter_short", "jitter_mongo_extra"}, 20: {"jitter_events"}}

    started, _ = live.configure(
        profiles, rows, enabled=enabled, window=8, from_mongo=True
    )
    updated = wait_for_layout(live, layout)
    for key, entry in before["entries"].items():
        assert_preserved(entry, updated["entries"][key], ("entry_id", "fingerprint"))
    assert_indexed_for_all(live, setup_splunk, started)

    removed_label = live.devices[0]["label"]
    deleted = [dict(row) for row in rows]
    deleted[0]["delete"] = "true"

    live.configure(profiles, deleted, enabled=enabled, window=8, from_mongo=True)
    remaining = {device["label"] for device in live.devices[1:]}
    wait_for_layout(live, layout, labels=remaining)

    started, _ = live.configure(
        profiles, rows, enabled=enabled, window=8, from_mongo=True
    )
    readded = wait_for_layout(live, layout)

    for key, entry in readded["entries"].items():
        previous = updated["entries"][key]
        if key.startswith(f"{removed_label}/"):
            assert entry["entry_id"] and entry["entry_id"] != previous["entry_id"]
        else:
            assert_preserved(previous, entry, ("entry_id", "fingerprint"))
    assert_indexed_for_all(live, setup_splunk, started)

    # The supported loader switches its source back to CSV while retaining Redis.
    before_csv = live.snapshot()

    live.configure(profiles, rows, enabled=enabled, window=8, from_mongo=False)
    after_csv = wait_for_layout(live, layout)
    assert_existing_schedules(before_csv, after_csv)
    for key, entry in before_csv["entries"].items():
        if entry["kind"] == "walk":
            assert_preserved(entry, after_csv["entries"][key])


@pytest.mark.part11
@pytest.mark.long_interval
@pytest.mark.parametrize("enabled", [False, True])
def test_profile_frequency_edits_cross_300_second_boundary(
    jitter_live, setup_splunk, enabled
):
    live = jitter_live

    profiles = {
        **delivery_profiles(),
        "jitter_boundary": {
            "frequency": 300,
            "varBinds": [["SNMPv2-MIB", "sysUpTime", 0]],
        },
        "jitter_touch_one": {
            "frequency": 10,
            "varBinds": [["SNMPv2-MIB", "sysName", 0]],
        },
        "jitter_touch_two": {
            "frequency": 10,
            "varBinds": [["SNMPv2-MIB", "sysName", 0]],
        },
    }
    rows = live.inventory("jitter_short;jitter_events;jitter_boundary")

    started, _ = live.configure(profiles, rows, enabled=enabled, window=8)
    before = wait_for_layout(
        live, {10: {"jitter_short"}, 20: {"jitter_events"}, 300: {"jitter_boundary"}}
    )
    wait_successful_polls(live)
    assert_indexed_for_all(live, setup_splunk, started)

    profiles["jitter_boundary"]["frequency"] = 301
    # A normal assignment edit requests the WALK that reevaluates profile frequencies.
    rows = live.inventory("jitter_short;jitter_events;jitter_boundary;jitter_touch_one")
    event_start = len(live.events)

    started, _ = live.configure(profiles, rows, enabled=enabled, window=8)
    longer = wait_for_layout(
        live,
        {
            10: {"jitter_short", "jitter_touch_one"},
            20: {"jitter_events"},
            301: {"jitter_boundary"},
        },
    )

    for device in live.devices:
        label = device["label"]
        assert (
            longer["entries"][f"{label}/poll/301"]["entry_id"]
            != before["entries"][f"{label}/poll/300"]["entry_id"]
        )
        for kind, frequency in (("walk", 1800), ("poll", 10), ("poll", 20)):
            key = f"{label}/{kind}/{frequency}"
            assert_preserved(
                before["entries"][key],
                longer["entries"][key],
                ("entry_id", "fingerprint"),
            )
    wait_successful_polls(live, event_start, frequencies=(301,))
    assert_indexed_for_all(live, setup_splunk, started)

    profiles["jitter_boundary"]["frequency"] = 300
    rows = live.inventory("jitter_short;jitter_events;jitter_boundary;jitter_touch_two")
    event_start = len(live.events)

    started, _ = live.configure(profiles, rows, enabled=enabled, window=8)
    shorter = wait_for_layout(
        live,
        {
            10: {"jitter_short", "jitter_touch_two"},
            20: {"jitter_events"},
            300: {"jitter_boundary"},
        },
    )

    for device in live.devices:
        label = device["label"]
        current = shorter["entries"][f"{label}/poll/300"]
        assert current["entry_id"] != before["entries"][f"{label}/poll/300"]["entry_id"]
        assert current["entry_id"] != longer["entries"][f"{label}/poll/301"]["entry_id"]
        assert current["count"] == 0 and not current["immediate"]
        assert current["due"] >= started + 300
    # Exactly 300 seconds retains the ordinary initial interval wait.
    wait_successful_polls(live, event_start, frequencies=(300,))
    assert_indexed_for_all(live, setup_splunk, started)


@pytest.mark.part15
@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("full_walk", [False, True])
def test_full_or_custom_walk_scope_and_scope_changes(
    jitter_live, setup_splunk, enabled, full_walk
):
    live = jitter_live

    profiles = {
        **delivery_profiles(),
        "jitter_system_walk": {
            "condition": {"type": "walk"},
            "varBinds": [["SNMPv2-MIB"]],
        },
        "jitter_interface_walk": {
            "condition": {"type": "walk"},
            "varBinds": [["SNMPv2-MIB"], ["IF-MIB"]],
        },
    }
    rows = live.inventory("jitter_short;jitter_events;jitter_system_walk")

    started, _ = live.configure(
        profiles, rows, enabled=enabled, window=8, full_walk=full_walk
    )
    before = wait_for_layout(live, {10: {"jitter_short"}, 20: {"jitter_events"}})
    expected_scope = None if full_walk else "jitter_system_walk"

    for entry in before["entries"].values():
        if entry["kind"] == "walk":
            assert entry["walk_profile"] == expected_scope
    wait_successful_polls(live)
    assert_indexed_for_all(live, setup_splunk, started)

    changed = live.inventory("jitter_short;jitter_events;jitter_interface_walk")

    started, _ = live.configure(
        profiles, changed, enabled=enabled, window=8, full_walk=full_walk
    )
    expected_scope = None if full_walk else "jitter_interface_walk"

    def updated_scope():
        snapshot = live.snapshot()
        if set(snapshot["entries"]) != set(before["entries"]):
            return None
        for key, previous in before["entries"].items():
            current = snapshot["entries"][key]
            if previous["kind"] == "walk" and (
                current["walk_profile"] != expected_scope
                or current["count"] <= previous["count"]
            ):
                return None
        return snapshot

    after = wait_for(
        updated_scope, "the updated WALK scope to complete setup", live.timeout
    )
    for key, entry in before["entries"].items():
        assert_preserved(entry, after["entries"][key], ("entry_id", "fingerprint"))
    assert_indexed_for_all(live, setup_splunk, started)
    assert_indexed_field(live, setup_splunk, started, "sc4snmp.IF-MIB.ifNumber", None)


@pytest.mark.part10
@pytest.mark.parametrize("enabled", [False, True])
def test_csv_same_frequency_profile_membership_updates(jitter_live, enabled):
    live = jitter_live

    profiles = short_profiles()
    for name in ("jitter_previous", "jitter_replacement"):
        profiles[name] = {
            "frequency": 10,
            "varBinds": [["SNMPv2-MIB", "sysDescr", 0]],
        }

    live.configure(
        profiles,
        live.inventory("jitter_short;jitter_previous"),
        enabled=enabled,
        window=8,
    )
    before = wait_for_layout(live, {10: {"jitter_short", "jitter_previous"}})

    live.configure(
        profiles,
        live.inventory("jitter_short;jitter_replacement"),
        enabled=enabled,
        window=8,
    )
    after = wait_for_layout(live, {10: {"jitter_short", "jitter_replacement"}})
    for key in before["entries"]:
        assert_preserved(before["entries"][key], after["entries"][key], ("entry_id",))


@pytest.mark.part10
@pytest.mark.parametrize("enabled", [False, True])
def test_csv_last_assignment_removes_obsolete_frequency(jitter_live, enabled):
    live = jitter_live

    profiles = short_profiles()
    profiles["jitter_twenty"] = {
        "frequency": 20,
        "varBinds": [["SNMPv2-MIB", "sysName", 0]],
    }

    live.configure(
        profiles,
        live.inventory("jitter_short;jitter_twenty"),
        enabled=enabled,
        window=8,
    )
    before = wait_for_layout(live, {10: {"jitter_short"}, 20: {"jitter_twenty"}})

    live.configure(profiles, live.inventory(), enabled=enabled, window=8)
    after = wait_for_layout(live, {10: {"jitter_short"}})
    for key, entry in after["entries"].items():
        assert_preserved(before["entries"][key], entry, ("entry_id",))


@pytest.mark.part10
@pytest.mark.parametrize("enabled", [False, True])
def test_csv_removing_all_assignments_leaves_valid_walk_only_devices(
    jitter_live, enabled
):
    live = jitter_live

    profiles = short_profiles()

    live.configure(profiles, live.inventory(), enabled=enabled, window=8)
    before = wait_for_layout(live, {10: {"jitter_short"}})

    live.configure(profiles, live.inventory(""), enabled=enabled, window=8)
    # Existing POLLs disappear only after the updated WALK reaches normal setup.
    after = wait_for_layout(live, {})
    for key, entry in after["entries"].items():
        assert_preserved(before["entries"][key], entry, ("entry_id",))


@pytest.mark.part10
@pytest.mark.parametrize("enabled", [False, True])
def test_csv_walk_interval_edit_keeps_schedule_identity(jitter_live, enabled):
    live = jitter_live

    profiles = short_profiles()
    profiles["jitter_after_interval_edit"] = {
        "frequency": 10,
        "varBinds": [["SNMPv2-MIB", "sysDescr", 0]],
    }

    live.configure(profiles, live.inventory(interval=1800), enabled=enabled, window=8)
    before = wait_for_layout(live, {10: {"jitter_short"}})

    live.configure(
        profiles,
        live.inventory("jitter_short;jitter_after_interval_edit", interval=3600),
        enabled=enabled,
        window=8,
    )
    after = wait_for_layout(
        live, {10: {"jitter_short", "jitter_after_interval_edit"}}, walk_interval=3600
    )
    for device in live.devices:
        label = device["label"]
        assert_preserved(
            before["entries"][f"{label}/walk/1800"],
            after["entries"][f"{label}/walk/3600"],
            ("entry_id",),
        )
        assert_preserved(
            before["entries"][f"{label}/poll/10"],
            after["entries"][f"{label}/poll/10"],
            ("entry_id",),
        )


@pytest.mark.part10
@pytest.mark.parametrize("enabled", [False, True])
def test_csv_delete_and_readd_creates_new_entry_ids(jitter_live, enabled):
    live = jitter_live

    profiles = short_profiles()
    rows = live.inventory(interval=1800)

    live.configure(profiles, rows, enabled=enabled, window=8)
    before = wait_for_layout(live, {10: {"jitter_short"}})
    deleted = [dict(row) for row in rows]
    deleted[0]["delete"] = "true"

    live.configure(profiles, deleted, enabled=enabled, window=8)
    removed_label = live.devices[0]["label"]
    remaining_keys = {
        key for key in before["entries"] if not key.startswith(f"{removed_label}/")
    }
    wait_for(
        lambda: set(live.snapshot()["entries"]) == remaining_keys,
        "normal inventory deletion of the selected simulator",
        live.timeout,
    )

    live.configure(profiles, rows, enabled=enabled, window=8)
    after = wait_for_layout(live, {10: {"jitter_short"}})

    for key, entry in after["entries"].items():
        previous = before["entries"][key]
        if key.startswith(f"{removed_label}/"):
            assert entry["entry_id"] and entry["entry_id"] != previous["entry_id"]
        else:
            assert_preserved(previous, entry, ("entry_id",))


@pytest.mark.part15
@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("smart_profiles", [False, True])
@pytest.mark.parametrize("poll_base", [False, True])
def test_smart_base_mandatory_and_conditional_assignments(
    jitter_live, enabled, smart_profiles, poll_base
):
    live = jitter_live

    profiles = {
        "jitter_static": {
            "frequency": 10,
            "varBinds": [["SNMPv2-MIB", "sysName", 0]],
        },
        "jitter_matching_smart": {
            "frequency": 10,
            "condition": {
                "type": "field",
                "field": "SNMPv2-MIB.sysDescr",
                "patterns": ["SC4SNMP autodiscovery integration.*"],
            },
            "varBinds": [["SNMPv2-MIB", "sysDescr", 0]],
        },
        "jitter_nonmatching_smart": {
            "frequency": 30,
            "condition": {
                "type": "field",
                "field": "SNMPv2-MIB.sysDescr",
                "patterns": ["^not-a-jitter-simulator$"],
            },
            "varBinds": [["SNMPv2-MIB", "sysName", 0]],
        },
        "jitter_base": {
            "frequency": 40,
            "condition": {"type": "base"},
            "varBinds": [["SNMPv2-MIB", "sysUpTime", 0]],
        },
        "jitter_mandatory": {
            "frequency": 20,
            "condition": {"type": "mandatory"},
            "varBinds": [["SNMPv2-MIB", "sysName", 0]],
        },
        "jitter_conditional": {
            "frequency": 20,
            "conditions": [
                {"field": "IF-MIB.ifAdminStatus", "operation": "equals", "value": "up"},
                {"field": "IF-MIB.ifOperStatus", "operation": "equals", "value": "up"},
            ],
            "varBinds": [["IF-MIB", "ifDescr"]],
        },
        "jitter_interface_walk": {
            "condition": {"type": "walk"},
            "varBinds": [
                ["SNMPv2-MIB"],
                ["IF-MIB", "ifDescr"],
                ["IF-MIB", "ifAdminStatus"],
                ["IF-MIB", "ifOperStatus"],
            ],
        },
    }
    rows = live.inventory(
        "jitter_static;jitter_conditional;jitter_interface_walk",
        interval=1800,
        smart_profiles=str(smart_profiles).lower(),
    )

    live.configure(profiles, rows, enabled=enabled, window=8, poll_base=poll_base)
    frequencies = (10, 20, 40) if smart_profiles and poll_base else (10, 20)
    expected_keys = {
        f"{device['label']}/{kind}/{interval}"
        for device in live.devices
        for kind, interval in [("walk", 1800)]
        + [("poll", frequency) for frequency in frequencies]
    }

    def assigned_after_walk():
        snapshot = live.snapshot()
        entries = snapshot["entries"]
        if set(entries) != expected_keys:
            return None
        for device in live.devices:
            label = device["label"]
            expected_short = {"jitter_static"}
            if smart_profiles:
                expected_short.add("jitter_matching_smart")
            if set(entries[f"{label}/poll/10"]["profiles"]) != expected_short:
                return None
            conditional = set(entries[f"{label}/poll/20"]["profiles"])
            # Generated names contain the endpoint, so match only their stable prefix.
            if (
                len(conditional) != 2
                or "jitter_mandatory" not in conditional
                or sum(name.startswith("jitter_conditional__") for name in conditional)
                != 1
            ):
                return None
            if 40 in frequencies and entries[f"{label}/poll/40"]["profiles"] != [
                "jitter_base"
            ]:
                return None
        return snapshot

    snapshot = wait_for(
        assigned_after_walk,
        "smart, base, mandatory and conditional assignments for every simulator",
        live.timeout,
    )
    devices = {device["label"]: device for device in live.devices}

    for entry in snapshot["entries"].values():
        assert entry["entry_id"]
        if enabled:
            assert_entry_policy(entry, devices[entry["label"]], 8)
        else:
            assert entry["fingerprint"] is None
