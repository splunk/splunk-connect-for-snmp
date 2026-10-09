from unittest import TestCase
from unittest.mock import ANY, Mock, patch

from redbeat.schedulers import RedBeatSchedulerEntry

from splunk_connect_for_snmp.enrich.tasks import check_restart

ENRICH_LOGGER = "splunk_connect_for_snmp.enrich.tasks"
CUSTOMTASKMANAGER_LOGGER = "splunk_connect_for_snmp.customtaskmanager"


def _sysuptime_result(value, group_key="SOME_KEY"):
    return {
        group_key: {
            "metrics": {
                "SNMPv2-MIB.sysUpTime": {
                    "value": value,
                    "type": "m",
                    "oid": "1.2.3.4.5",
                }
            }
        }
    }


class TestEnrich(TestCase):
    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    def test_check_restart(self, m_task_manager):
        periodic_obj_mock = Mock()
        periodic_obj_mock.walk_task_exists.return_value = True
        m_task_manager.return_value = periodic_obj_mock
        current_target = {"sysUpTime": {"value": 40}}
        targets_collection = Mock()

        check_restart(
            current_target, _sysuptime_result(30), targets_collection, "192.168.0.1"
        )

        periodic_obj_mock.walk_task_exists.assert_called_once_with("192.168.0.1")
        periodic_obj_mock.manage_task.assert_called_once_with(
            name="sc4snmp;192.168.0.1;walk", run_immediately=True
        )
        calls = targets_collection.update_one.call_args_list
        self.assertEqual({"address": "192.168.0.1"}, calls[0][0][0])
        self.assertEqual(
            {"$set": {"sysUpTime": {"value": 30, "type": "m", "oid": "1.2.3.4.5"}}},
            calls[0][0][1],
        )

    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    def test_check_restart_not_applied(self, m_task_manager):
        periodic_obj_mock = Mock()
        m_task_manager.return_value = periodic_obj_mock
        current_target = {"sysUpTime": {"value": 40}}
        targets_collection = Mock()

        check_restart(
            current_target, _sysuptime_result(50), targets_collection, "192.168.0.1"
        )

        periodic_obj_mock.walk_task_exists.assert_not_called()
        periodic_obj_mock.manage_task.assert_not_called()

        calls = targets_collection.update_one.call_args_list
        self.assertEqual({"address": "192.168.0.1"}, calls[0][0][0])
        self.assertEqual(
            {"$set": {"sysUpTime": {"value": 50, "type": "m", "oid": "1.2.3.4.5"}}},
            calls[0][0][1],
        )

    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    def test_check_restart_walk_task_missing(self, m_task_manager):
        periodic_obj_mock = Mock()
        periodic_obj_mock.walk_task_exists.return_value = False
        m_task_manager.return_value = periodic_obj_mock
        current_target = {"sysUpTime": {"value": 40}}
        targets_collection = Mock()

        with self.assertLogs(ENRICH_LOGGER, level="WARNING") as logs:
            check_restart(
                current_target,
                _sysuptime_result(30),
                targets_collection,
                "192.168.0.1",
            )

        periodic_obj_mock.manage_task.assert_not_called()
        self.assertIn("192.168.0.1", logs.output[0])
        self.assertIn("sc4snmp;192.168.0.1;walk", logs.output[0])

        calls = targets_collection.update_one.call_args_list
        self.assertEqual({"address": "192.168.0.1"}, calls[0][0][0])
        self.assertEqual(
            {"$set": {"sysUpTime": {"value": 30, "type": "m", "oid": "1.2.3.4.5"}}},
            calls[0][0][1],
        )

    @patch("splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager")
    def test_check_restart_walk_trigger_failure_still_updates_sysuptime(
        self, m_task_manager
    ):
        current_target = {"sysUpTime": {"value": 40}}

        cases = {
            "walk_task_exists raises": lambda m: setattr(
                m.walk_task_exists, "side_effect", ConnectionError("redis down")
            ),
            "manage_task raises": lambda m: (
                setattr(m.walk_task_exists, "return_value", True),
                setattr(
                    m.manage_task,
                    "side_effect",
                    AttributeError("'NoneType' object has no attribute 'now'"),
                ),
            ),
        }
        for description, configure_mock in cases.items():
            with self.subTest(description):
                periodic_obj_mock = Mock()
                configure_mock(periodic_obj_mock)
                m_task_manager.return_value = periodic_obj_mock
                targets_collection = Mock()

                with self.assertLogs(ENRICH_LOGGER, level="ERROR"):
                    check_restart(
                        current_target,
                        _sysuptime_result(30),
                        targets_collection,
                        "192.168.0.1",
                    )

                calls = targets_collection.update_one.call_args_list
                self.assertEqual(
                    {
                        "$set": {
                            "sysUpTime": {"value": 30, "type": "m", "oid": "1.2.3.4.5"}
                        }
                    },
                    calls[0][0][1],
                )

    def test_check_restart_missing_walk_entry_breaks_restart_loop(self):
        """
        End-to-end regression test for the historical crash: with no
        CustomPeriodicTaskManager mocked out, a missing walk entry used to
        raise AttributeError from inside RedBeatSchedulerEntry's constructor.
        It must not raise, and once sysUpTime is persisted, the same restart
        must not be re-detected on the next poll.
        """
        targets_collection = Mock()
        with patch.object(
            RedBeatSchedulerEntry, "from_key", side_effect=KeyError
        ) as m_from_key, patch.object(
            RedBeatSchedulerEntry, "save", autospec=True
        ) as m_save:
            check_restart(
                {"sysUpTime": {"value": 40}},
                _sysuptime_result(30),
                targets_collection,
                "192.168.0.1:161",
            )

        m_from_key.assert_called_once_with(
            "redbeat:sc4snmp;192.168.0.1:161;walk", app=ANY
        )
        m_save.assert_not_called()
        first_state = targets_collection.update_one.call_args_list[0][0][1]
        self.assertEqual(30, first_state["$set"]["sysUpTime"]["value"])

        # Next poll: current_target now reflects the persisted value, so the
        # same restart must not be detected (and from_key not called) again.
        with patch.object(
            RedBeatSchedulerEntry, "from_key", side_effect=KeyError
        ) as m_from_key_2:
            check_restart(
                {"sysUpTime": first_state["$set"]["sysUpTime"]},
                _sysuptime_result(60),
                targets_collection,
                "192.168.0.1:161",
            )

        m_from_key_2.assert_not_called()
        self.assertEqual(2, targets_collection.update_one.call_count)

    def test_check_restart_walk_entry_deleted_after_existence_check(self):
        """
        Regression test for the check-then-use race: walk_task_exists can
        return True and the entry can still be gone by the time manage_task
        looks it up itself. manage_task's own guard (not enrich's catch) must
        handle this.
        """
        targets_collection = Mock()
        with patch(
            "splunk_connect_for_snmp.customtaskmanager.CustomPeriodicTaskManager"
            ".walk_task_exists",
            return_value=True,
        ), patch.object(
            RedBeatSchedulerEntry, "from_key", side_effect=KeyError
        ), patch.object(
            RedBeatSchedulerEntry, "save", autospec=True
        ) as m_save, self.assertLogs(
            CUSTOMTASKMANAGER_LOGGER, level="ERROR"
        ) as logs:
            check_restart(
                {"sysUpTime": {"value": 40}},
                _sysuptime_result(30),
                targets_collection,
                "192.168.0.1:161",
            )

        m_save.assert_not_called()
        self.assertTrue(logs.output[0].endswith("missing task, schedule, app"))
