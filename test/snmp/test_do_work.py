from unittest import TestCase
from unittest.mock import patch, Mock

from splunk_connect_for_snmp.snmp.manager import Poller


# class TestDoWork(TestCase):
#     def test_do_Work(self):
#         poller = Poller.__new__(Poller)
#
#         varbinds_bulk = set()
#         varbinds_get = set()
#         get_mapping = {}
#         bulk_mapping = {}
#
#         poller.get_var_binds.return_value = varbinds_get, get_mapping, varbinds_bulk, bulk_mapping
#
#         #poller.do_work("192.168.0.1", )