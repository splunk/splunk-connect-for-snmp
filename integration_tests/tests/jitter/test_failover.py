import pytest

from integration_tests.tests.jitter.checks import assert_preserved
from integration_tests.tests.jitter.delivery import (
    assert_indexed_for_all,
    delivery_profiles,
    wait_successful_polls,
)
from integration_tests.utils.polling import wait_for

pytestmark = pytest.mark.part12


@pytest.mark.parametrize("action", ["failover_redis", "step_down_mongo"])
def test_primary_failover_preserves_schedules_and_resumes_delivery(
    jitter_live, request, action
):
    live = jitter_live

    setup_splunk = request.getfixturevalue("setup_splunk")

    started, _ = live.configure(
        delivery_profiles(),
        live.inventory("jitter_short;jitter_events"),
        enabled=True,
        window=8,
    )
    before = live.wait_entries(len(live.devices) * 3)["entries"]
    wait_successful_polls(live)
    assert_indexed_for_all(live, setup_splunk, started)
    promotion = live.probe(action, timeout=max(1, live.timeout - 5))

    assert promotion["requested"] is True
    assert promotion["changed_primary"] is True

    def recovered():
        try:
            snapshot = live.snapshot()
        except RuntimeError:
            return None
        return snapshot if len(snapshot["entries"]) == len(live.devices) * 3 else None

    after = wait_for(
        recovered, "schedule access after primary promotion", live.timeout
    )["entries"]
    for key in before:
        assert_preserved(before[key], after[key], fields=("entry_id", "fingerprint"))
    # Reconnect only the observation stream, never warm-restart a sender to hide
    # an unresolved delivery stall after promotion.
    live.stop_events()
    event_start = len(live.events)
    live.start_events()
    wait_successful_polls(live, event_start)
    assert_indexed_for_all(live, setup_splunk, promotion["completed_at"])
