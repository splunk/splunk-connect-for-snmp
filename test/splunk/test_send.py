from unittest import TestCase
from unittest.mock import patch

from splunk_connect_for_snmp.splunk.tasks import do_send, send

test_data = {"events": [], "metrics": []}
for j in range(1, 3):
    test_data["events"].append(str(j))
    test_data["metrics"].append(str(j + 100))


class TestSend(TestCase):
    @patch("splunk_connect_for_snmp.splunk.tasks.HECTask")
    def test_chunking(self, m_hec_task):
        data = []
        for i in range(1, 180):
            data.append(str(i))

        do_send(data, "MY_TEST_URL", m_hec_task)

        expected1 = "\n".join(str(i) for i in range(1, 51))
        expected2 = "\n".join(str(i) for i in range(51, 101))
        expected3 = "\n".join(str(i) for i in range(101, 151))
        expected4 = "\n".join(str(i) for i in range(151, 180))

        calls = m_hec_task.session.post.call_args_list
        self.assertEqual("MY_TEST_URL", calls[0][0][0])
        self.assertEqual(expected1, calls[0][1]["data"])
        self.assertEqual(60, calls[0][1]["timeout"])

        self.assertEqual("MY_TEST_URL", calls[1][0][0])
        self.assertEqual(expected2, calls[1][1]["data"])
        self.assertEqual(60, calls[1][1]["timeout"])

        self.assertEqual("MY_TEST_URL", calls[2][0][0])
        self.assertEqual(expected3, calls[2][1]["data"])
        self.assertEqual(60, calls[2][1]["timeout"])

        self.assertEqual("MY_TEST_URL", calls[3][0][0])
        self.assertEqual(expected4, calls[3][1]["data"])
        self.assertEqual(60, calls[3][1]["timeout"])

    @patch("splunk_connect_for_snmp.splunk.tasks.SPLUNK_HEC_TOKEN", "some_token")
    @patch("splunk_connect_for_snmp.splunk.tasks.OTEL_METRICS_URL", None)
    @patch("splunk_connect_for_snmp.splunk.tasks.SPLUNK_HEC_URI", "my_test_uri")
    @patch("splunk_connect_for_snmp.splunk.tasks.HECTask")
    @patch("splunk_connect_for_snmp.splunk.tasks.do_send")
    def test_send_only_splunk(self, m_do_send, m_hec_task):
        send(test_data)

        calls = m_do_send.call_args_list

        self.assertEqual(2, len(calls))

        self.assertEqual(["1", "2"], calls[0][0][0])
        self.assertEqual("my_test_uri", calls[0][0][1])

        self.assertEqual(["101", "102"], calls[1][0][0])
        self.assertEqual("my_test_uri", calls[1][0][1])

    @patch("splunk_connect_for_snmp.splunk.tasks.SPLUNK_HEC_TOKEN", None)
    @patch("splunk_connect_for_snmp.splunk.tasks.OTEL_METRICS_URL", "my_otel_uri")
    @patch("splunk_connect_for_snmp.splunk.tasks.SPLUNK_HEC_URI", "my_test_uri")
    @patch("splunk_connect_for_snmp.splunk.tasks.HECTask")
    @patch("splunk_connect_for_snmp.splunk.tasks.do_send")
    def test_send_only_sim(self, m_do_send, m_hec_task):
        send(test_data)

        calls = m_do_send.call_args_list

        self.assertEqual(1, len(calls))

        self.assertEqual(["101", "102"], calls[0][0][0])
        self.assertEqual("my_otel_uri", calls[0][0][1])

    @patch("splunk_connect_for_snmp.splunk.tasks.SPLUNK_HEC_TOKEN", "some_token")
    @patch("splunk_connect_for_snmp.splunk.tasks.OTEL_METRICS_URL", "my_otel_uri")
    @patch("splunk_connect_for_snmp.splunk.tasks.SPLUNK_HEC_URI", "my_test_uri")
    @patch("splunk_connect_for_snmp.splunk.tasks.HECTask")
    @patch("splunk_connect_for_snmp.splunk.tasks.do_send")
    def test_send_splunk_and_sim(self, m_do_send, m_hec_task):
        send(test_data)

        calls = m_do_send.call_args_list

        self.assertEqual(3, len(calls))

        self.assertEqual(["1", "2"], calls[0][0][0])
        self.assertEqual("my_test_uri", calls[0][0][1])

        self.assertEqual(["101", "102"], calls[1][0][0])
        self.assertEqual("my_test_uri", calls[1][0][1])

        self.assertEqual(["101", "102"], calls[2][0][0])
        self.assertEqual("my_otel_uri", calls[2][0][1])
