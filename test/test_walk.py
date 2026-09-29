from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, mock_open, patch

from splunk_connect_for_snmp.walk import run_walk

mock_inventory = """address,port,version,community,secret,securityEngine,walk_interval,profiles,SmartProfiles,delete
localhost,,2c,public,,,1804,test_1,True,False
#localhost,,2c,public,,,1804,test_1,True,False
192.178.0.1,,2c,public,,,1804,test_1,True,False"""


class TestWalk(IsolatedAsyncioTestCase):
    @patch("builtins.open", new_callable=mock_open, read_data=mock_inventory)
    @patch("splunk_connect_for_snmp.walk.Poller._ensure_worker_initialized")
    @patch(
        "splunk_connect_for_snmp.snmp.manager.Poller.do_work", new_callable=AsyncMock
    )
    async def test_run_walk(self, m_do_work, m_ensure_initialized, m_open):
        m_do_work.return_value = (False, {})

        await run_walk()

        m_ensure_initialized.assert_called_once_with()
        calls = m_do_work.call_args_list

        self.assertEqual(2, len(calls))

        self.assertEqual({"is_walk": True}, calls[0][1])
        self.assertEqual({"is_walk": True}, calls[1][1])

        self.assertEqual("localhost", calls[0].args[0].address)
        self.assertEqual("192.178.0.1", calls[1].args[0].address)

    @patch("builtins.open", new_callable=mock_open, read_data=mock_inventory)
    @patch("splunk_connect_for_snmp.walk.Poller._ensure_worker_initialized")
    @patch(
        "splunk_connect_for_snmp.snmp.manager.Poller.do_work", new_callable=AsyncMock
    )
    async def test_run_walk_exception(self, m_do_work, m_ensure_initialized, m_open):
        m_do_work.side_effect = (Exception("Boom!"), (False, {}))

        await run_walk()

        m_ensure_initialized.assert_called_once_with()
        calls = m_do_work.call_args_list

        self.assertEqual(2, len(calls))

        self.assertEqual({"is_walk": True}, calls[0][1])
        self.assertEqual({"is_walk": True}, calls[1][1])

        self.assertEqual("localhost", calls[0].args[0].address)
        self.assertEqual("192.178.0.1", calls[1].args[0].address)
