import json
from unittest import TestCase
from unittest.mock import patch

from splunk_connect_for_snmp.splunk.tasks import apply_custom_translations, prepare


@patch("splunk_connect_for_snmp.splunk.tasks.SPLUNK_HEC_INDEX_EVENTS", "test_index")
@patch("splunk_connect_for_snmp.splunk.tasks.SPLUNK_HEC_INDEX_METRICS", "test_index_2")
class TestPrepare(TestCase):
    @patch("splunk_connect_for_snmp.splunk.tasks.apply_custom_translations")
    def test_prepare_trap(self, m_custom):
        task_input = {
            "sourcetype": "sc4snmp:traps",
            "time": 1234567,
            "address": "192.168.0.1",
            "result": {
                "SOME_GROUP_KEY1": {
                    "metrics": {
                        "metric_one": {"value": 23},
                        "metric_two": {"value": 26},
                    },
                    "fields": {
                        "field_one": {"value": "on"},
                        "field_two": {"value": "listening"},
                    },
                },
                "SOME_GROUP_KEY2": {
                    "metrics": {
                        "metric_three": {"value": 67},
                        "metric_four": {"value": 90},
                    },
                    "fields": {
                        "field_three": {"value": "OFF"},
                        "field_four": {"value": "stopping"},
                    },
                },
            },
        }

        m_custom.return_value = task_input
        result = prepare(task_input)

        self.assertEqual("list", type(result["events"]).__name__)

        item1 = json.loads(result["events"][0])
        event1 = json.loads(item1["event"])
        item1["event"] = event1
        result["events"][0] = item1

        item2 = json.loads(result["events"][1])
        event2 = json.loads(item2["event"])
        item2["event"] = event2
        result["events"][1] = item2

        self.assertEqual(
            {
                "events": [
                    {
                        "time": 1234567,
                        "event": {
                            "field_one": {"value": "on"},
                            "field_two": {"value": "listening"},
                            "metric_one": {"value": 23.0},
                            "metric_two": {"value": 26.0},
                        },
                        "source": "sc4snmp",
                        "sourcetype": "sc4snmp:traps",
                        "host": "192.168.0.1",
                        "index": "test_index",
                    },
                    {
                        "time": 1234567,
                        "event": {
                            "field_three": {"value": "OFF"},
                            "field_four": {"value": "stopping"},
                            "metric_three": {"value": 67.0},
                            "metric_four": {"value": 90.0},
                        },
                        "source": "sc4snmp",
                        "sourcetype": "sc4snmp:traps",
                        "host": "192.168.0.1",
                        "index": "test_index",
                    },
                ],
                "metrics": [],
            },
            result,
        )

    @patch("splunk_connect_for_snmp.splunk.tasks.SPLUNK_AGGREGATE_TRAPS_EVENTS", True)
    @patch("splunk_connect_for_snmp.splunk.tasks.apply_custom_translations")
    def test_prepare_aggregated_trap(self, m_custom):
        task_input = {
            "sourcetype": "sc4snmp:traps",
            "time": 1234567,
            "address": "192.168.0.1",
            "result": {
                "SOME_GROUP_KEY1": {
                    "metrics": {
                        "metric_one": {"value": 23},
                        "metric_two": {"value": 26},
                    },
                    "fields": {
                        "field_one": {"value": "on"},
                        "field_two": {"value": "listening"},
                    },
                },
                "SOME_GROUP_KEY2": {
                    "metrics": {
                        "metric_three": {"value": 67},
                        "metric_four": {"value": 90},
                    },
                    "fields": {
                        "field_three": {"value": "OFF"},
                        "field_four": {"value": "stopping"},
                    },
                },
            },
        }

        m_custom.return_value = task_input
        result = prepare(task_input)

        self.assertEqual("list", type(result["events"]).__name__)

        item1 = json.loads(result["events"][0])
        event1 = json.loads(item1["event"])
        item1["event"] = event1
        result["events"][0] = item1

        self.assertEqual(
            {
                "events": [
                    {
                        "time": 1234567,
                        "event": {
                            "field_one": {"value": "on"},
                            "field_two": {"value": "listening"},
                            "metric_one": {"value": 23.0},
                            "metric_two": {"value": 26.0},
                            "field_three": {"value": "OFF"},
                            "field_four": {"value": "stopping"},
                            "metric_three": {"value": 67.0},
                            "metric_four": {"value": 90.0},
                        },
                        "source": "sc4snmp",
                        "sourcetype": "sc4snmp:traps",
                        "host": "192.168.0.1",
                        "index": "test_index",
                    }
                ],
                "metrics": [],
            },
            result,
        )

    @patch("splunk_connect_for_snmp.splunk.tasks.METRICS_INDEXING_ENABLED", True)
    @patch("splunk_connect_for_snmp.splunk.tasks.apply_custom_translations")
    def test_prepare_metrics(self, m_custom):
        task_input = {
            "time": 1234567,
            "address": "192.168.0.1",
            "frequency": 15,
            "result": {
                "SOME_GROUP_KEY1": {
                    "indexes": [6],
                    "metrics": {
                        "metric_one": {"value": 23},
                        "metric_two": {"value": 26},
                    },
                    "fields": {
                        "field_one": {"value": "on"},
                        "field_two": {"value": "listening"},
                    },
                    "profiles": "profile1,profile2",
                },
                "SOME_GROUP_KEY2": {
                    "metrics": {
                        "metric_three": {"value": 67},
                        "metric_four": {"value": 90},
                    },
                    "fields": {
                        "field_three": {"value": "OFF"},
                        "field_four": {"value": "stopping"},
                    },
                    "profiles": "profile1,profile2",
                },
            },
        }

        m_custom.return_value = task_input
        result = prepare(task_input)

        self.assertEqual("list", type(result["metrics"]).__name__)

        item1 = json.loads(result["metrics"][0])
        result["metrics"][0] = item1

        item2 = json.loads(result["metrics"][1])
        result["metrics"][1] = item2

        self.assertEqual(
            {
                "metrics": [
                    {
                        "time": 1234567,
                        "event": "metric",
                        "source": "sc4snmp",
                        "sourcetype": "sc4snmp:metric",
                        "host": "192.168.0.1",
                        "index": "test_index_2",
                        "fields": {
                            "frequency": 15,
                            "profiles": "profile1,profile2",
                            "field_one": "on",
                            "field_two": "listening",
                            "metric_name:sc4snmp.metric_one": 23.0,
                            "metric_name:sc4snmp.metric_two": 26.0,
                            "mibIndex": "6",
                        },
                    },
                    {
                        "time": 1234567,
                        "event": "metric",
                        "source": "sc4snmp",
                        "sourcetype": "sc4snmp:metric",
                        "host": "192.168.0.1",
                        "index": "test_index_2",
                        "fields": {
                            "frequency": 15,
                            "profiles": "profile1,profile2",
                            "field_three": "OFF",
                            "field_four": "stopping",
                            "metric_name:sc4snmp.metric_three": 67.0,
                            "metric_name:sc4snmp.metric_four": 90.0,
                        },
                    },
                ],
                "events": [],
            },
            result,
        )

    @patch("splunk_connect_for_snmp.splunk.tasks.apply_custom_translations")
    def test_prepare_metrics_no_indexing(self, m_custom):
        task_input = {
            "time": 1234567,
            "address": "192.168.0.1",
            "frequency": 15,
            "result": {
                "SOME_GROUP_KEY1": {
                    "metrics": {
                        "metric_one": {"value": 23},
                        "metric_two": {"value": 26, "index": "6"},
                    },
                    "fields": {
                        "field_one": {"value": "on"},
                        "field_two": {"value": "listening"},
                    },
                    "profiles": "profile1,profile2",
                },
                "SOME_GROUP_KEY2": {
                    "metrics": {
                        "metric_three": {"value": 67},
                        "metric_four": {"value": 90},
                    },
                    "fields": {
                        "field_three": {"value": "OFF"},
                        "field_four": {"value": "stopping"},
                    },
                    "profiles": "profile1,profile2",
                },
            },
        }

        m_custom.return_value = task_input
        result = prepare(task_input)

        self.assertEqual("list", type(result["metrics"]).__name__)
        self.assertEqual(2, len(result))
        self.assertEqual(0, len(result["events"]))
        self.assertEqual(2, len(result["metrics"]))

        item1 = json.loads(result["metrics"][0])
        fields1 = item1["fields"]
        self.assertNotIn("mibIndex", fields1)

    @patch("splunk_connect_for_snmp.splunk.tasks.apply_custom_translations")
    def test_prepare_metrics_group(self, m_custom):
        task_input = {
            "time": 1234567,
            "address": "192.168.0.1",
            "frequency": 15,
            "group": "group1",
            "result": {
                "SOME_GROUP_KEY1": {
                    "metrics": {
                        "metric_one": {"value": 23},
                        "metric_two": {"value": 26},
                    },
                    "fields": {
                        "field_one": {"value": "on"},
                        "field_two": {"value": "listening"},
                    },
                    "profiles": "profile1,profile2",
                },
                "SOME_GROUP_KEY2": {
                    "metrics": {
                        "metric_three": {"value": 67},
                        "metric_four": {"value": 90},
                    },
                    "fields": {
                        "field_three": {"value": "OFF"},
                        "field_four": {"value": "stopping"},
                    },
                    "profiles": "profile1,profile2",
                },
            },
        }

        m_custom.return_value = task_input
        result = prepare(task_input)

        self.assertEqual("list", type(result["metrics"]).__name__)

        item1 = json.loads(result["metrics"][0])
        result["metrics"][0] = item1

        item2 = json.loads(result["metrics"][1])
        result["metrics"][1] = item2

        self.assertEqual(
            {
                "metrics": [
                    {
                        "time": 1234567,
                        "event": "metric",
                        "source": "sc4snmp",
                        "sourcetype": "sc4snmp:metric",
                        "host": "192.168.0.1",
                        "index": "test_index_2",
                        "fields": {
                            "frequency": 15,
                            "profiles": "profile1,profile2",
                            "group": "group1",
                            "field_one": "on",
                            "field_two": "listening",
                            "metric_name:sc4snmp.metric_one": 23.0,
                            "metric_name:sc4snmp.metric_two": 26.0,
                        },
                    },
                    {
                        "time": 1234567,
                        "event": "metric",
                        "source": "sc4snmp",
                        "sourcetype": "sc4snmp:metric",
                        "host": "192.168.0.1",
                        "index": "test_index_2",
                        "fields": {
                            "frequency": 15,
                            "profiles": "profile1,profile2",
                            "group": "group1",
                            "field_three": "OFF",
                            "field_four": "stopping",
                            "metric_name:sc4snmp.metric_three": 67.0,
                            "metric_name:sc4snmp.metric_four": 90.0,
                        },
                    },
                ],
                "events": [],
            },
            result,
        )

    @patch("splunk_connect_for_snmp.splunk.tasks.apply_custom_translations")
    def test_prepare_only_events(self, m_custom):
        task_input = {
            "time": 1234567,
            "address": "192.168.0.1",
            "result": {
                "SOME_GROUP_KEY1": {
                    "fields": {
                        "field_one": {"value": "on"},
                        "field_two": {"value": "listening"},
                    },
                    "metrics": {},
                },
                "SOME_GROUP_KEY2": {
                    "fields": {
                        "field_three": {"value": "OFF"},
                        "field_four": {"value": "stopping"},
                    },
                    "metrics": {},
                },
            },
        }

        m_custom.return_value = task_input
        result = prepare(task_input)

        self.assertEqual("list", type(result["metrics"]).__name__)

        item1 = json.loads(result["events"][0])
        event1 = json.loads(item1["event"])
        item1["event"] = event1
        result["events"][0] = item1

        item2 = json.loads(result["events"][1])
        event2 = json.loads(item2["event"])
        item2["event"] = event2
        result["events"][1] = item2

        self.assertEqual(
            {
                "metrics": [],
                "events": [
                    {
                        "time": 1234567,
                        "event": {
                            "field_one": {"value": "on"},
                            "field_two": {"value": "listening"},
                        },
                        "source": "sc4snmp",
                        "sourcetype": "sc4snmp:event",
                        "host": "192.168.0.1",
                        "index": "test_index",
                    },
                    {
                        "time": 1234567,
                        "event": {
                            "field_three": {"value": "OFF"},
                            "field_four": {"value": "stopping"},
                        },
                        "source": "sc4snmp",
                        "sourcetype": "sc4snmp:event",
                        "host": "192.168.0.1",
                        "index": "test_index",
                    },
                ],
            },
            result,
        )

    def test_apply_custom_translation(self):
        work = {
            "result": {
                "SOME_KEY": {
                    "fields": {
                        "SNMPv2-MIB.sysDescr": {
                            "oid": "9.8.7.6",
                            "time": 1640609779.473053,
                            "type": "r",
                            "value": "up and running",
                            "name": "SNMPv2-MIB.sysDescr",
                        },
                        "SNMPv2-MIB.some_other": {
                            "oid": "9.8.7.6.1",
                            "time": 1640609779.473053,
                            "type": "r",
                            "value": "ON",
                            "name": "SNMPv2-MIB.some_other",
                        },
                    },
                    "metrics": {
                        "IF-MIB.ifInDiscards": {
                            "oid": "1.2.3.4.5.6.7",
                            "time": 1640609779.473053,
                            "type": "g",
                            "value": 65.0,
                        }
                    },
                }
            }
        }

        translations = {
            "IF-MIB": {"ifInDiscards": "myCustomName1", "ifOutErrors": "myCustomName2"},
            "SNMPv2-MIB": {"sysDescr": "myCustomName3"},
        }

        result = apply_custom_translations(work, translations)

        self.assertEqual(
            {
                "result": {
                    "SOME_KEY": {
                        "fields": {
                            "SNMPv2-MIB.myCustomName3": {
                                "oid": "9.8.7.6",
                                "time": 1640609779.473053,
                                "type": "r",
                                "value": "up and running",
                                "name": "SNMPv2-MIB.myCustomName3",
                            },
                            "SNMPv2-MIB.some_other": {
                                "oid": "9.8.7.6.1",
                                "time": 1640609779.473053,
                                "type": "r",
                                "value": "ON",
                                "name": "SNMPv2-MIB.some_other",
                            },
                        },
                        "metrics": {
                            "IF-MIB.myCustomName1": {
                                "oid": "1.2.3.4.5.6.7",
                                "time": 1640609779.473053,
                                "type": "g",
                                "value": 65.0,
                            }
                        },
                    }
                }
            },
            result,
        )
