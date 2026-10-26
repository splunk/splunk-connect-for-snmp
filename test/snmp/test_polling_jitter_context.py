import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from splunk_connect_for_snmp.common.polling_jitter import (
    INITIAL_REGISTRATION,
    SCHEDULE_CONTEXT,
)


@pytest.mark.parametrize("context", [INITIAL_REGISTRATION, None, "unknown"])
def test_walk_context_reaches_callbacks_but_not_snmp_or_output(context):
    with patch(
        "splunk_connect_for_snmp.snmp.manager.Poller.__init__", return_value=None
    ), patch(
        "splunk_connect_for_snmp.common.custom_translations.load_custom_translations",
        return_value={},
    ):
        from splunk_connect_for_snmp.snmp.tasks import walk_async_wrapper
        from splunk_connect_for_snmp.splunk.tasks import prepare

    poller = Mock()
    poller.do_work = AsyncMock(
        return_value=(
            False,
            {
                "system": {
                    "fields": {},
                    "metrics": {"SNMPv2-MIB.sysUpTime": {"value": 1}},
                }
            },
        )
    )
    with patch("splunk_connect_for_snmp.snmp.tasks.get_mongo_client"), patch(
        "splunk_connect_for_snmp.snmp.tasks.get_inventory", return_value="inventory"
    ):
        work = asyncio.run(
            walk_async_wrapper(
                poller,
                address="router-01:161",
                profile="WalkProfile",
                **{SCHEDULE_CONTEXT: context}
            )
        )
    assert work.get(SCHEDULE_CONTEXT) == (
        INITIAL_REGISTRATION if context == INITIAL_REGISTRATION else None
    )
    poller.do_work.assert_awaited_once_with(
        "inventory", is_walk=True, profiles=["WalkProfile"]
    )
    with patch(
        "splunk_connect_for_snmp.splunk.tasks.load_custom_translations", return_value={}
    ), patch("splunk_connect_for_snmp.snmp.manager.Poller.__init__", return_value=None):
        output = prepare(work)
    assert SCHEDULE_CONTEXT not in json.dumps(output)
    assert INITIAL_REGISTRATION not in json.dumps(output)
