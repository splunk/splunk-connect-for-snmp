import json
from unittest import TestCase
from unittest.mock import patch

from splunk_connect_for_snmp.splunk.tasks import prepare, apply_custom_translations


@patch('splunk_connect_for_snmp.splunk.tasks.SPLUNK_HEC_INDEX_EVENTS', 'test_index')
@patch('splunk_connect_for_snmp.splunk.tasks.SPLUNK_HEC_INDEX_METRICS', 'test_index_2')
class TestPrepare(TestCase):
    def test_prepare_trap(self):
        task_input = {
            "sourcetype": "sc4snmp:traps",
            "time": 1234567,
            "address": "192.168.0.1",
            "result": {
                "SOME_GROUP_KEY1":
                    {
                        "metrics": {"metric_one": {"value": 23}, "metric_two": {"value": 26}},
                        "fields": {"field_one": {"value": "on"}, "field_two": {"value": "listening"}},
                    },
                "SOME_GROUP_KEY2":
                    {
                        "metrics": {"metric_three": {"value": 67}, "metric_four": {"value": 90}},
                        "fields": {"field_three": {"value": "OFF"}, "field_four": {"value": "stopping"}},
                    },
            }
        }

        result = prepare(task_input)

        self.assertEqual("list", type(result["events"]).__name__)
        self.assertEqual(2, len(result))
        self.assertEqual(2, len(result["events"]))
        self.assertEqual(0, len(result["metrics"]))

        item1 = json.loads(result["events"][0])
        event1 = json.loads(item1["event"])
        self.assertEqual(1234567, item1["time"])
        self.assertEqual("192.168.0.1", item1["host"])
        self.assertEqual("test_index", item1["index"])
        self.assertEqual("sc4snmp", item1["source"])
        self.assertEqual("sc4snmp:traps", item1["sourcetype"])
        self.assertEqual("192.168.0.1", item1["host"])
        self.assertEqual("on", event1["field_one"]["value"])
        self.assertEqual("listening", event1["field_two"]["value"])
        self.assertEqual(23.0, event1["metric_one"]["value"])
        self.assertEqual(26.0, event1["metric_two"]["value"])

        item2 = json.loads(result["events"][1])
        event2 = json.loads(item2["event"])

        self.assertEqual(1234567, item2["time"])
        self.assertEqual("192.168.0.1", item2["host"])
        self.assertEqual("test_index", item2["index"])
        self.assertEqual("sc4snmp", item2["source"])
        self.assertEqual("sc4snmp:traps", item2["sourcetype"])
        self.assertEqual("192.168.0.1", item2["host"])
        self.assertEqual("OFF", event2["field_three"]["value"])
        self.assertEqual("stopping", event2["field_four"]["value"])
        self.assertEqual(67.0, event2["metric_three"]["value"])
        self.assertEqual(90.0, event2["metric_four"]["value"])

    def test_prepare_metrics(self):
        task_input = {
            "time": 1234567,
            "address": "192.168.0.1",
            "frequency": 15,
            "result": {
                "SOME_GROUP_KEY1":
                    {
                        "metrics": {"metric_one": {"value": 23}, "metric_two": {"value": 26}},
                        "fields": {"field_one": {"value": "on"}, "field_two": {"value": "listening"}},
                        "profiles": "profile1,profile2",
                    },
                "SOME_GROUP_KEY2":
                    {
                        "metrics": {"metric_three": {"value": 67}, "metric_four": {"value": 90}},
                        "fields": {"field_three": {"value": "OFF"}, "field_four": {"value": "stopping"}},
                        "profiles": "profile1,profile2",
                    },
            }
        }

        result = prepare(task_input)

        self.assertEqual("list", type(result["metrics"]).__name__)
        self.assertEqual(2, len(result))
        self.assertEqual(0, len(result["events"]))
        self.assertEqual(2, len(result["metrics"]))

        item1 = json.loads(result["metrics"][0])
        fields1 = item1["fields"]
        self.assertEqual(1234567, item1["time"])
        self.assertEqual("192.168.0.1", item1["host"])
        self.assertEqual("test_index_2", item1["index"])
        self.assertEqual("sc4snmp", item1["source"])
        self.assertEqual("sc4snmp:metric", item1["sourcetype"])
        self.assertEqual("192.168.0.1", item1["host"])
        self.assertEqual("on", fields1["field_one"])
        self.assertEqual("listening", fields1["field_two"])
        self.assertEqual(23.0, fields1["metric_name:sc4snmp.metric_one"])
        self.assertEqual(26.0, fields1["metric_name:sc4snmp.metric_two"])
        self.assertEqual(15, fields1["frequency"])
        self.assertEqual("profile1,profile2", fields1["profiles"])

        item2 = json.loads(result["metrics"][1])
        fields2 = item2["fields"]
        self.assertEqual(1234567, item2["time"])
        self.assertEqual("192.168.0.1", item2["host"])
        self.assertEqual("test_index_2", item2["index"])
        self.assertEqual("sc4snmp", item2["source"])
        self.assertEqual("sc4snmp:metric", item2["sourcetype"])
        self.assertEqual("192.168.0.1", item2["host"])
        self.assertEqual("OFF", fields2["field_three"])
        self.assertEqual("stopping", fields2["field_four"])
        self.assertEqual(67, fields2["metric_name:sc4snmp.metric_three"])
        self.assertEqual(90, fields2["metric_name:sc4snmp.metric_four"])
        self.assertEqual(15, fields2["frequency"])
        self.assertEqual("profile1,profile2", fields2["profiles"])

    def test_prepare_only_events(self):
        task_input = {
            "time": 1234567,
            "address": "192.168.0.1",
            "result": {
                "SOME_GROUP_KEY1":
                    {
                        "fields": {"field_one": {"value": "on"}, "field_two": {"value": "listening"}},
                        "metrics": {},
                    },
                "SOME_GROUP_KEY2":
                    {
                        "fields": {"field_three": {"value": "OFF"}, "field_four": {"value": "stopping"}},
                        "metrics": {},
                    },
            }
        }

        result = prepare(task_input)

        self.assertEqual("list", type(result["metrics"]).__name__)
        self.assertEqual(2, len(result))
        self.assertEqual(2, len(result["events"]))
        self.assertEqual(0, len(result["metrics"]))

        item1 = json.loads(result["events"][0])
        event1 = json.loads(item1["event"])
        self.assertEqual(1234567, item1["time"])
        self.assertEqual("192.168.0.1", item1["host"])
        self.assertEqual("test_index", item1["index"])
        self.assertEqual("sc4snmp", item1["source"])
        self.assertEqual("sc4snmp:event", item1["sourcetype"])
        self.assertEqual("192.168.0.1", item1["host"])
        self.assertEqual("on", event1["field_one"]["value"])
        self.assertEqual("listening", event1["field_two"]["value"])

        item2 = json.loads(result["events"][1])
        event2 = json.loads(item2["event"])

        self.assertEqual(1234567, item2["time"])
        self.assertEqual("192.168.0.1", item2["host"])
        self.assertEqual("test_index", item2["index"])
        self.assertEqual("sc4snmp", item2["source"])
        self.assertEqual("sc4snmp:event", item2["sourcetype"])
        self.assertEqual("192.168.0.1", item2["host"])
        self.assertEqual("OFF", event2["field_three"]["value"])
        self.assertEqual("stopping", event2["field_four"]["value"])

    def test_apply_custom_translation(self):
        work = {"result": {"SOME_KEY": {'fields': {'SNMPv2-MIB.sysDescr': {'oid': '9.8.7.6',
                                                                           'time': 1640609779.473053,
                                                                           'type': 'r',
                                                                           'value': 'up and running',
                                                                           "name": 'SNMPv2-MIB.sysDescr'},
                                                   'SNMPv2-MIB.some_other': {'oid': '9.8.7.6.1',
                                                                             'time': 1640609779.473053,
                                                                             'type': 'r',
                                                                             'value': 'ON',
                                                                             "name": "SNMPv2-MIB.some_other"}},
                                        'metrics': {'IF-MIB.ifInDiscards': {'oid': '1.2.3.4.5.6.7',
                                                                            'time': 1640609779.473053,
                                                                            'type': 'g',
                                                                            'value': 65.0}}}}}

        translations = {"IF-MIB": {"ifInDiscards": "myCustomName1", "ifOutErrors": "myCustomName2"},
                        "SNMPv2-MIB": {"sysDescr": "myCustomName3"}}

        result = apply_custom_translations(work, translations)

        self.assertEqual({"result": {"SOME_KEY": {'fields': {'SNMPv2-MIB.myCustomName3': {'oid': '9.8.7.6',
                                                                                          'time': 1640609779.473053,
                                                                                          'type': 'r',
                                                                                          'value': 'up and running',
                                                                                          "name": 'SNMPv2-MIB.myCustomName3'},
                                                             'SNMPv2-MIB.some_other': {'oid': '9.8.7.6.1',
                                                                                       'time': 1640609779.473053,
                                                                                       'type': 'r',
                                                                                       'value': 'ON',
                                                                                       "name": "SNMPv2-MIB.some_other"}},
                                                  'metrics': {'IF-MIB.myCustomName1': {'oid': '1.2.3.4.5.6.7',
                                                                                       'time': 1640609779.473053,
                                                                                       'type': 'g',
                                                                                       'value': 65.0}}}}}, result)
