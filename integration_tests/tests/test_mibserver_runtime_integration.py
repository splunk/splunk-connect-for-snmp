import json
import time
from datetime import datetime, timezone

import pytest
from pysnmp.hlapi.v3arch.asyncio import OctetString

from integration_tests.utils.mibserver import (
    configured_local_mib_directory,
    install_refresh_test_mib,
    prepare_local_mib_environment,
    wait_for_refresh_mib_index_row,
)
from integration_tests.utils.splunk_test_utils import (
    assert_splunk_search_absent,
    restart_worker_for_mib_index_refresh,
    wait_for_mib_refresh_worker_log,
    wait_for_splunk_search,
    wait_for_trap_receiver_ready,
)
from integration_tests.utils.traps import send_trap

pytestmark = pytest.mark.part9

REFRESH_POLLER_OID = "1.3.6.1.4.1.42705.2.1.0"
REFRESH_POLLER_FIELD = "HVR-MIB.hvrPollerStatus.value"
REFRESH_POLLER_VALUE = "local-mib-refresh-poller"
REFRESH_POLLER_CONTROL_FIELD = "SNMPv2-MIB.sysDescr.value"
REFRESH_POLLER_CONTROL_VALUE = "local-mib-refresh-control"
REFRESH_NOTIFICATION_OID = "1.3.6.1.4.1.42705.1.3.0.1"
REFRESH_NUMERIC_NOTIFICATION = "SNMPv2-SMI::enterprises.42705.1.3.0.1"
REFRESH_RESOLVED_NOTIFICATION = "HVR-MIB::hvrAlertNotifySummary"
LOCAL_MIB_SCALAR_VALUES = (
    ("sc4snmpTestObject", "local-mib-poller", 1),
    ("sc4snmpTestLevel", -5, 2),
    ("sc4snmpTestState", "ready-state", 3),
    ("sc4snmpTestBits", "first, ninth", 4),
    ("sc4snmpTestOid", "SC4SNMP-TEST-MIB::sc4snmpTestIdentity", 10),
    ("sc4snmpTestHex", "0xabcd", 12),
    ("sc4snmpTestBinary", "0xaa", 13),
)


def _poller_field_search(host, field, value, earliest):
    return f"""search index="netops" sourcetype="sc4snmp:event"
        host="{host}" earliest={earliest} "{field}"="{value}" | head 1"""


def _wait_for_poller_field(service, host, field, expected_value, earliest, timeout=180):
    wait_for_splunk_search(
        service,
        _poller_field_search(host, field, expected_value, earliest),
        f"{field!r}={expected_value!r} from {host}",
        timeout,
    )


def _assert_poller_field_absent(service, host, field, value, earliest):
    assert_splunk_search_absent(
        service,
        _poller_field_search(host, field, value, earliest),
        f"poller field {field!r}={value!r} from {host}",
    )


def _trap_value_search(marker, value):
    return f"""search index="netops" sourcetype="sc4snmp:traps" earliest=-5m
        "SNMPv2-MIB.sysDescr.value"="{marker}"
        "SNMPv2-MIB.snmpTrapOID.value"="{value}" | head 1"""


def _wait_for_trap_value(service, marker, expected_value, timeout=120):
    wait_for_splunk_search(
        service,
        _trap_value_search(marker, expected_value),
        f"trap {marker!r} to resolve as {expected_value!r}",
        timeout,
    )


def _assert_trap_value_absent(service, marker, unexpected_value):
    assert_splunk_search_absent(
        service,
        _trap_value_search(marker, unexpected_value),
        f"trap {marker!r} indexed as {unexpected_value!r}",
    )


async def _send_refresh_trap(host, marker):
    await send_trap(
        host,
        162,
        REFRESH_NOTIFICATION_OID,
        "SNMPv2-MIB",
        "public",
        1,
        ("1.3.6.1.2.1.1.1.0", OctetString(marker)),
    )


@pytest.fixture(scope="module")
def local_mib_runtime_environment(request):
    deployment = request.config.getoption("sc4snmp_deployment")
    host = request.config.getoption("trap_external_ip")
    prepare_local_mib_environment(deployment)
    return deployment, host, f"{host}:1166"


@pytest.mark.asyncio
async def test_local_mib_is_resolved_after_worker_restart(
    local_mib_runtime_environment, setup_splunk
):
    deployment, host, target = local_mib_runtime_environment
    local_mibs_dir = configured_local_mib_directory(deployment)
    wait_for_refresh_mib_index_row(deployment, expected_present=False)
    for worker_type in ("poller", "trap"):
        restart_worker_for_mib_index_refresh(deployment, worker_type)
    wait_for_trap_receiver_ready(deployment)

    started_at = datetime.now(timezone.utc)
    earliest = int(started_at.timestamp())
    log_start = started_at.isoformat().replace("+00:00", "Z")
    install_refresh_test_mib(deployment, local_mibs_dir)

    _wait_for_poller_field(
        setup_splunk,
        target,
        REFRESH_POLLER_CONTROL_FIELD,
        REFRESH_POLLER_CONTROL_VALUE,
        earliest,
    )
    _assert_poller_field_absent(
        setup_splunk,
        target,
        REFRESH_POLLER_FIELD,
        REFRESH_POLLER_VALUE,
        earliest,
    )
    wait_for_mib_refresh_worker_log(
        deployment,
        "poller",
        log_start,
        ("no mib found", REFRESH_POLLER_OID, f"from {target}"),
        f"worker-poller to report an unresolved {REFRESH_POLLER_OID} "
        f"lookup from {target}",
    )
    marker = f"mib_refresh_unresolved_{time.time_ns()}"
    await _send_refresh_trap(host, marker)
    _wait_for_trap_value(setup_splunk, marker, REFRESH_NUMERIC_NOTIFICATION)
    _assert_trap_value_absent(setup_splunk, marker, REFRESH_RESOLVED_NOTIFICATION)

    earliest = int(time.time())
    restart_worker_for_mib_index_refresh(deployment, "poller")
    _wait_for_poller_field(
        setup_splunk,
        target,
        REFRESH_POLLER_FIELD,
        REFRESH_POLLER_VALUE,
        earliest,
    )
    restart_worker_for_mib_index_refresh(deployment, "trap")
    marker = f"mib_refresh_resolved_{time.time_ns()}"
    await _send_refresh_trap(host, marker)
    _wait_for_trap_value(setup_splunk, marker, REFRESH_RESOLVED_NOTIFICATION)
    _assert_trap_value_absent(setup_splunk, marker, REFRESH_NUMERIC_NOTIFICATION)


def test_poller_local_mib_scalar_get_and_restart(
    local_mib_runtime_environment, setup_splunk
):
    deployment, _, target = local_mib_runtime_environment
    earliest = int(time.time())
    conditions = " ".join(
        f'"SC4SNMP-TEST-MIB.{symbol}.value"={json.dumps(value)} '
        f'"SC4SNMP-TEST-MIB.{symbol}.oid"="1.3.6.1.4.1.99999.{oid}.0"'
        for symbol, value, oid in LOCAL_MIB_SCALAR_VALUES
    )

    def wait_for_scalar_event(since):
        wait_for_splunk_search(
            setup_splunk,
            f'search index="netops" sourcetype="sc4snmp:event" '
            f'host="{target}" earliest={since} {conditions} | head 1',
            "a local MIB scalar event with translated values and exact OIDs",
        )

    wait_for_scalar_event(earliest)
    restart_worker_for_mib_index_refresh(deployment, "poller")
    wait_for_scalar_event(int(time.time()) + 1)


@pytest.mark.parametrize("mode", ["symbolic", "discovered"])
def test_poller_local_mib_walks_and_metrics(
    local_mib_runtime_environment, setup_splunk, mode
):
    _, _, target = local_mib_runtime_environment
    earliest = int(time.time())
    profile_filter = (
        'profiles="local_mib_symbolic" ' if mode == "symbolic" else "frequency=11 "
    )

    def wait_for_metrics(expected):
        conditions = " ".join(
            f'"{field}"={json.dumps(value)}' for field, value in expected.items()
        )
        wait_for_splunk_search(
            setup_splunk,
            f"| mpreview index=netmetrics earliest={earliest} "
            f'| search host="{target}" sourcetype="sc4snmp:metric" '
            f"{profile_filter}{conditions} | head 1",
            "local MIB metrics with matching row labels and values",
        )

    scalar_fields = {symbol: value for symbol, value, _ in LOCAL_MIB_SCALAR_VALUES}
    scalar_fields["sc4snmpTestAddress"] = "0.0.0.0"
    for symbol, value in (
        ("sc4snmpTestCounter", 12345),
        ("sc4snmpTestLargeCounter", 4294967301),
        ("sc4snmpTestGauge", 42),
        ("sc4snmpTestTicks", 123456),
        ("sc4snmpTestUnsigned", 17),
    ):
        wait_for_metrics(
            {f"metric_name:sc4snmp.SC4SNMP-TEST-MIB.{symbol}": value, **scalar_fields}
        )
    for label, base_value, augmented_value in (
        ("alpha", 4294967311, 73),
        ("beta", 4294967312, 74),
    ):
        wait_for_metrics(
            {
                "metric_name:sc4snmp.SC4SNMP-TEST-MIB.sc4snmpTestValue": base_value,
                "sc4snmpTestDescription": f"local-row-{label}",
            }
        )
        wait_for_metrics(
            {
                "metric_name:sc4snmp.SC4SNMP-TEST-EXT-MIB.sc4snmpTestExtra": augmented_value,
                "sc4snmpTestExtraLabel": f"local-augmented-{label}",
            }
        )
