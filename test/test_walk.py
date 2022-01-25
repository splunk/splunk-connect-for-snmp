from unittest import TestCase
from unittest.mock import MagicMock, mock_open, patch

from splunk_connect_for_snmp.walk import run_walk

mock_inventory = """address,port,version,community,secret,securityEngine,walk_interval,profiles,SmartProfiles,delete
localhost,,2c,public,,,1804,test_1,True,False
#localhost,,2c,public,,,1804,test_1,True,False
192.178.0.1,,2c,public,,,1804,test_1,True,False"""


class TestWalk(TestCase):
    @patch("builtins.open", new_callable=mock_open, read_data=mock_inventory)
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.__init__")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.do_work")
    @patch("splunk_connect_for_snmp.snmp.manager.load_profiles")
    def test_run_walk(self, m_load_profiles, m_do_work, m_init, m_open):
        m_init.return_value = None
        m_do_work.return_value = (False, {})

        run_walk()

        calls = m_do_work.call_args_list

        self.assertEqual(2, len(calls))

        self.assertEqual({"walk": True}, calls[0][1])
        self.assertEqual({"walk": True}, calls[1][1])

        self.assertEqual("localhost", calls[0].args[0].address)
        self.assertEqual("192.178.0.1", calls[1].args[0].address)

    @patch("builtins.open", new_callable=mock_open, read_data=mock_inventory)
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.__init__")
    @patch("splunk_connect_for_snmp.snmp.manager.Poller.do_work")
    @patch("splunk_connect_for_snmp.snmp.manager.load_profiles")
    def test_run_walk_exception(self, m_load_profiles, m_do_work, m_init, m_open):
        m_init.return_value = None
        m_do_work.side_effect = (Exception("Boom!"), (False, {}))

        run_walk()

        calls = m_do_work.call_args_list

        self.assertEqual(2, len(calls))

        self.assertEqual({"walk": True}, calls[0][1])
        self.assertEqual({"walk": True}, calls[1][1])

        self.assertEqual("localhost", calls[0].args[0].address)
        self.assertEqual("192.178.0.1", calls[1].args[0].address)
