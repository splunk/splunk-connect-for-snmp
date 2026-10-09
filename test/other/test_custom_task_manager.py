from unittest import TestCase
from unittest.mock import ANY, Mock, patch

from celery.schedules import schedule

from splunk_connect_for_snmp.customtaskmanager import (
    DISCOVERY_TASK,
    POLL_TASK,
    REQUIRED_NEW_TASK_FIELDS,
    WALK_TASK,
    CustomPeriodicTaskManager,
    _get_all_schedules,
    _get_schedules_by_target,
    _load_schedules,
)


def mock_schedules(m_get_all_schedules, options, options_by_type=None):
    options_by_type = options_by_type or {}
    schedules = {}
    for task_type in (WALK_TASK, POLL_TASK, DISCOVERY_TASK):
        schedule_entry = Mock()
        schedule_entry.task = task_type
        schedule_entry.name = f"sc4snmp;{task_type}"
        schedule_entry.options = options_by_type.get(task_type, options)
        schedules[task_type] = schedule_entry
    m_get_all_schedules.return_value = list(schedules.values())
    return schedules


class TestLoadSchedules(TestCase):
    @patch("redbeat.schedulers.RedBeatSchedulerEntry.from_key")
    @patch("splunk_connect_for_snmp.customtaskmanager.get_redis")
    def test_skips_keyerror_without_losing_others(self, m_get_redis, m_from_key):
        m_get_redis.return_value.scan_iter.return_value = [
            "redbeat:sc4snmp;a;walk",
            "redbeat:sc4snmp;orphan;walk",
            "redbeat:sc4snmp;b;walk",
        ]
        good_a, good_b = Mock(), Mock()

        def from_key_side_effect(key, app=None):
            if key == "redbeat:sc4snmp;orphan;walk":
                raise KeyError(key)
            return {"redbeat:sc4snmp;a;walk": good_a, "redbeat:sc4snmp;b;walk": good_b}[
                key
            ]

        m_from_key.side_effect = from_key_side_effect

        with self.assertLogs(
            "splunk_connect_for_snmp.customtaskmanager", level="WARNING"
        ) as logs:
            result = _load_schedules("redbeat:sc4snmp;*")

        self.assertEqual([good_a, good_b], result)
        self.assertIn("redbeat:sc4snmp;orphan;walk", logs.output[0])

    @patch("redbeat.schedulers.RedBeatSchedulerEntry.from_key")
    @patch("splunk_connect_for_snmp.customtaskmanager.get_redis")
    def test_skips_invalid_json(self, m_get_redis, m_from_key):
        m_get_redis.return_value.scan_iter.return_value = [
            "redbeat:sc4snmp;good;walk",
            "redbeat:sc4snmp;corrupt;walk",
        ]
        good = Mock()

        def from_key_side_effect(key, app=None):
            if key == "redbeat:sc4snmp;corrupt;walk":
                raise ValueError("Expecting value")
            return good

        m_from_key.side_effect = from_key_side_effect

        with self.assertLogs(
            "splunk_connect_for_snmp.customtaskmanager", level="WARNING"
        ) as logs:
            result = _load_schedules("redbeat:sc4snmp;*")

        self.assertEqual([good], result)
        self.assertIn("redbeat:sc4snmp;corrupt;walk", logs.output[0])

    @patch("splunk_connect_for_snmp.customtaskmanager.get_redis")
    def test_propagates_connection_error(self, m_get_redis):
        m_get_redis.return_value.scan_iter.side_effect = ConnectionError("redis down")

        with self.assertRaises(ConnectionError):
            _load_schedules("redbeat:sc4snmp;*")

    @patch("splunk_connect_for_snmp.customtaskmanager._load_schedules")
    def test_get_all_schedules_pattern(self, m_load):
        _get_all_schedules()
        m_load.assert_called_once_with("redbeat:sc4snmp;*")

    @patch("splunk_connect_for_snmp.customtaskmanager._load_schedules")
    def test_get_schedules_by_target_pattern(self, m_load):
        _get_schedules_by_target("192.168.0.1:161")
        m_load.assert_called_once_with("*192.168.0.1:161;*")


class TestCustomTaskManager(TestCase):
    @patch("splunk_connect_for_snmp.customtaskmanager._get_schedules_by_target")
    def test_delete_unused_poll_tasks(self, m_objects):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)
        task1 = Mock()
        task1.task = "splunk_connect_for_snmp.snmp.tasks.poll"
        task1.name = "test1"

        task2 = Mock()
        task2.task = "splunk_connect_for_snmp.snmp.tasks.poll"
        task2.name = "test2"

        task3 = Mock()
        task3.task = "splunk_connect_for_snmp.snmp.tasks.walk"
        task3.name = "test3"

        task4 = Mock()
        task4.task = "splunk_connect_for_snmp.snmp.tasks.poll"
        task4.name = "name1"

        m_objects.return_value = [task1, task2, task3, task4]

        task_manager.delete_unused_poll_tasks("192.168.0.1", ["name1", "name2"])
        m_objects.assert_called_with("192.168.0.1")
        self.assertTrue(task1.delete.called)
        self.assertTrue(task2.delete.called)
        self.assertFalse(task3.delete.called)
        self.assertFalse(task4.delete.called)

    @patch("redbeat.schedulers.RedBeatSchedulerEntry.from_key")
    @patch("splunk_connect_for_snmp.customtaskmanager.get_redis")
    def test_delete_unused_poll_tasks_skips_orphan(self, m_get_redis, m_from_key):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)
        target = "192.168.0.1:161"
        m_get_redis.return_value.scan_iter.return_value = [
            f"redbeat:sc4snmp;{target};orphan-walk",
            f"redbeat:sc4snmp;{target};poll;30",
        ]
        poll = Mock()
        poll.task = POLL_TASK
        poll.name = f"sc4snmp;{target};poll;30"

        def from_key_side_effect(key, app=None):
            if "orphan" in key:
                raise KeyError(key)
            return poll

        m_from_key.side_effect = from_key_side_effect

        task_manager.delete_unused_poll_tasks(target, [])

        poll.delete.assert_called_once()

    @patch("splunk_connect_for_snmp.customtaskmanager._get_all_schedules")
    def test_delete_unused_discovery_tasks(self, m_objects):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)
        active = Mock()
        active.task = DISCOVERY_TASK
        active.name = "sc4snmp;active;discovery"

        removed = Mock()
        removed.task = DISCOVERY_TASK
        removed.name = "sc4snmp;removed;discovery"

        walk = Mock()
        walk.task = WALK_TASK
        walk.name = "sc4snmp;192.168.0.1:161;walk"

        m_objects.return_value = [active, removed, walk]

        task_manager.delete_unused_discovery_tasks(["sc4snmp;active;discovery"])

        removed.delete.assert_called_once()
        active.delete.assert_not_called()
        walk.delete.assert_not_called()

    @patch("redbeat.schedulers.RedBeatSchedulerEntry.from_key")
    @patch("splunk_connect_for_snmp.customtaskmanager.get_redis")
    def test_delete_unused_discovery_tasks_skips_orphan(self, m_get_redis, m_from_key):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)
        m_get_redis.return_value.scan_iter.return_value = [
            "redbeat:sc4snmp;orphan;walk",
            "redbeat:sc4snmp;removed;discovery",
        ]
        removed = Mock()
        removed.task = DISCOVERY_TASK
        removed.name = "sc4snmp;removed;discovery"

        def from_key_side_effect(key, app=None):
            if "orphan" in key:
                raise KeyError(key)
            return removed

        m_from_key.side_effect = from_key_side_effect

        task_manager.delete_unused_discovery_tasks([])

        removed.delete.assert_called_once()

    @patch("redbeat.schedulers.RedBeatSchedulerEntry.from_key")
    def test_manage_existing_task(self, redbeat_scheduler_entry_from_key):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)

        task1 = Mock()
        task1.name = "test1"
        task1.schedule = schedule(120)
        task1.save = Mock()

        redbeat_scheduler_entry_from_key.return_value = task1

        task_data = {
            "task": "task1",
            "name": "test1",
            "args": {"arg1": "val1", "arg2": "val2"},
            "kwargs": {"karg1": "val1", "karg2": "val2"},
            "schedule": schedule(60),
            "target": "some_target",
            "options": "some+option",
            "enabled": True,
            "run_immediately": False,
        }

        task_manager.manage_task(**task_data)

        redbeat_scheduler_entry_from_key.assert_called_with("redbeat:test1", app=ANY)
        self.assertEqual(task1.schedule, schedule(60))
        self.assertTrue(task1.save.called)

    @patch("redbeat.schedulers.RedBeatSchedulerEntry.from_key")
    @patch("redbeat.schedulers.RedBeatSchedulerEntry.__new__")
    def test_manage_new_task(self, redbeat_scheduler, redbeat_scheduler_entry_from_key):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)

        redbeat_scheduler_entry_from_key.side_effect = KeyError

        task1 = Mock()
        task_data = {
            "task": "task1",
            "name": "test1",
            "args": {"arg1": "val1", "arg2": "val2"},
            "kwargs": {"karg1": "val1", "karg2": "val2"},
            "schedule": schedule(60),
            "target": "some_target",
            "options": "some+option",
            "enabled": True,
            "run_immediately": False,
            "app": Mock(),
        }

        redbeat_scheduler.return_value = task1
        task_manager.manage_task(**task_data)

        redbeat_scheduler_entry_from_key.assert_called_with("redbeat:test1", app=ANY)
        self.assertTrue(task1.save.called)
        task1.reschedule.assert_not_called()

    @patch("redbeat.schedulers.RedBeatSchedulerEntry.from_key")
    def test_manage_new_task_incomplete_definition_is_skipped(
        self, redbeat_scheduler_entry_from_key
    ):
        """
        Regression test for the historical crash: enrich/tasks.py's
        check_restart only ever sends name + run_immediately for a walk that
        turns out to be missing. The real RedBeatSchedulerEntry constructor
        is NOT mocked here, so this proves the guard, not a mock, prevents it.
        """
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)
        redbeat_scheduler_entry_from_key.side_effect = KeyError

        with patch(
            "redbeat.schedulers.RedBeatSchedulerEntry.save", autospec=True
        ) as m_save, self.assertLogs(
            "splunk_connect_for_snmp.customtaskmanager", level="ERROR"
        ) as logs:
            task_manager.manage_task(
                name="sc4snmp;192.168.0.1:161;walk", run_immediately=True
            )

        m_save.assert_not_called()
        self.assertTrue(logs.output[0].endswith("missing task, schedule, app"))

    @patch("redbeat.schedulers.RedBeatSchedulerEntry.from_key")
    def test_manage_new_task_missing_required_field(
        self, redbeat_scheduler_entry_from_key
    ):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)
        redbeat_scheduler_entry_from_key.side_effect = KeyError
        complete_task_data = {
            "name": "test1",
            "task": "task1",
            "schedule": schedule(60),
            "app": Mock(),
            "args": [],
            "kwargs": {},
            "run_immediately": False,
        }

        for field in REQUIRED_NEW_TASK_FIELDS:
            with self.subTest(field):
                task_data = {**complete_task_data, field: None}
                with patch(
                    "redbeat.schedulers.RedBeatSchedulerEntry.save", autospec=True
                ) as m_save, self.assertLogs(
                    "splunk_connect_for_snmp.customtaskmanager", level="ERROR"
                ) as logs:
                    task_manager.manage_task(**task_data)

                m_save.assert_not_called()
                self.assertTrue(logs.output[0].endswith(f"missing {field}"))

    @patch("redbeat.schedulers.RedBeatSchedulerEntry.from_key")
    def test_manage_task_existing_target(self, redbeat_scheduler_entry_from_key):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)

        task1 = Mock()
        task1.name = "test1"
        task1.target = "some_target"
        task1.save = Mock()

        redbeat_scheduler_entry_from_key.return_value = task1

        task_data = {
            "task": "task1",
            "name": "test1",
            "args": {"arg1": "val1", "arg2": "val2"},
            "kwargs": {"karg1": "val1", "karg2": "val2"},
            "schedule": schedule(60),
            "target": "some_other_target",
            "options": "some+option",
            "enabled": True,
            "run_immediately": False,
        }

        task_manager.manage_task(**task_data)

        redbeat_scheduler_entry_from_key.assert_called_with("redbeat:test1", app=ANY)
        self.assertEqual(task1.target, "some_other_target")
        self.assertTrue(task1.save.called)

    @patch("redbeat.schedulers.RedBeatSchedulerEntry.from_key")
    @patch("redbeat.schedulers.RedBeatSchedulerEntry.__new__")
    def test_manage_task_existing_only_props(
        self, redbeat_scheduler, redbeat_scheduler_entry_from_key
    ):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)

        task1 = Mock()
        task1.name = "test1"
        task1.task = ("task1",)
        task1.args = ({"arg1": "val1", "arg2": "val2"},)
        task1.kwargs = ({"karg1": "val1", "karg2": "val2"},)
        task1.schedule = (schedule(60),)
        task1.target = ("some_other_target",)
        task1.options = ("some+option",)
        task1.enabled = (True,)
        task1.run_immediately = (False,)

        redbeat_scheduler_entry_from_key.return_value = task1
        new_args = {"arg1": "new_arg_value"}
        new_kwargs = {"karg1": "new_karg_value"}
        new_task_data = {
            "task": "task1",
            "name": "test1",
            "args": new_args,
            "kwargs": new_kwargs,
            "schedule": schedule(60),
            "target": "some_other_target",
            "options": "some+option",
            "enabled": True,
            "run_immediately": False,
        }

        task_manager.manage_task(**new_task_data)

        self.assertEqual(task1.args, new_args)
        self.assertEqual(task1.kwargs, new_kwargs)

        redbeat_scheduler.assert_not_called()
        task1.save.assert_called()

    @patch("splunk_connect_for_snmp.customtaskmanager._get_all_schedules")
    def test_delete_all_poll_tasks(self, m_objects):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)
        task1 = Mock()
        task1.task = "splunk_connect_for_snmp.snmp.tasks.poll"
        task1.name = "test1"

        task2 = Mock()
        task2.task = "splunk_connect_for_snmp.snmp.tasks.poll"
        task2.name = "test2"

        task3 = Mock()
        task3.task = "splunk_connect_for_snmp.snmp.tasks.walk"
        task3.name = "test3"

        m_objects.return_value = [task1, task2, task3]
        task_manager.delete_all_poll_tasks()
        self.assertTrue(task1.delete.called)
        self.assertTrue(task2.delete.called)
        self.assertFalse(task3.delete.called)

    @patch("redbeat.schedulers.RedBeatSchedulerEntry.from_key")
    @patch("splunk_connect_for_snmp.customtaskmanager.get_redis")
    def test_delete_all_poll_tasks_skips_orphan(self, m_get_redis, m_from_key):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)
        m_get_redis.return_value.scan_iter.return_value = [
            "redbeat:sc4snmp;orphan;walk",
            "redbeat:sc4snmp;a;poll",
            "redbeat:sc4snmp;b;poll",
        ]
        poll_a, poll_b = Mock(), Mock()
        poll_a.task = POLL_TASK
        poll_b.task = POLL_TASK

        def from_key_side_effect(key, app=None):
            if "orphan" in key:
                raise KeyError(key)
            return {
                "redbeat:sc4snmp;a;poll": poll_a,
                "redbeat:sc4snmp;b;poll": poll_b,
            }[key]

        m_from_key.side_effect = from_key_side_effect

        task_manager.delete_all_poll_tasks()

        poll_a.delete.assert_called_once()
        poll_b.delete.assert_called_once()

    @patch("splunk_connect_for_snmp.customtaskmanager._get_all_schedules")
    def test_get_chain_of_task_expiries(self, m_objects):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)
        discovery = Mock()
        discovery.task = DISCOVERY_TASK
        discovery.options = {"expires": 300}

        walk = Mock()
        walk.task = WALK_TASK
        walk.options = {"expires": 120}

        poll = Mock()
        poll.task = POLL_TASK
        poll.options = {"expires": 60}

        no_expiry_poll = Mock()
        no_expiry_poll.task = POLL_TASK
        no_expiry_poll.options = {}

        m_objects.return_value = [discovery, walk, poll, no_expiry_poll]
        self.assertEqual(
            {60, 120}, task_manager.get_chain_of_task_expiries([WALK_TASK, POLL_TASK])
        )
        self.assertEqual(
            {300}, task_manager.get_chain_of_task_expiries([DISCOVERY_TASK])
        )

        m_objects.return_value = [walk]
        self.assertEqual(
            set(), task_manager.get_chain_of_task_expiries([DISCOVERY_TASK])
        )

        m_objects.return_value = []
        self.assertEqual(set(), task_manager.get_chain_of_task_expiries([WALK_TASK]))

        m_objects.return_value = [no_expiry_poll]
        self.assertEqual(set(), task_manager.get_chain_of_task_expiries([POLL_TASK]))

    @patch("splunk_connect_for_snmp.customtaskmanager._get_all_schedules")
    def test_did_expiry_time_change_deletes_only_polling_tasks(self, m_objects):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)
        entries = mock_schedules(m_objects, {"expires": 120})

        did_time_change = task_manager.did_expiry_time_change(
            300, [WALK_TASK, POLL_TASK]
        )

        self.assertTrue(did_time_change)
        entries[WALK_TASK].delete.assert_called_once()
        entries[POLL_TASK].delete.assert_called_once()
        entries[DISCOVERY_TASK].delete.assert_not_called()

    @patch("splunk_connect_for_snmp.customtaskmanager._get_all_schedules")
    def test_did_expiry_time_change_deletes_only_discovery_tasks(self, m_objects):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)
        entries = mock_schedules(m_objects, {"expires": 120})

        did_time_change = task_manager.did_expiry_time_change(300, [DISCOVERY_TASK])

        self.assertTrue(did_time_change)
        entries[DISCOVERY_TASK].delete.assert_called_once()
        entries[WALK_TASK].delete.assert_not_called()
        entries[POLL_TASK].delete.assert_not_called()

    @patch("splunk_connect_for_snmp.customtaskmanager._get_all_schedules")
    def test_did_expiry_time_change_mixed_expiry_times(self, m_objects):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)
        mixed = {WALK_TASK: {"expires": 300}, POLL_TASK: {"expires": 60}}

        for configured_expiry in (300, 60):
            with self.subTest(configured_expiry=configured_expiry):
                entries = mock_schedules(
                    m_objects, {"expires": 300}, options_by_type=mixed
                )

                did_time_change = task_manager.did_expiry_time_change(
                    configured_expiry, [WALK_TASK, POLL_TASK]
                )

                self.assertTrue(did_time_change)
                entries[WALK_TASK].delete.assert_called_once()
                entries[POLL_TASK].delete.assert_called_once()
                entries[DISCOVERY_TASK].delete.assert_not_called()

    @patch("splunk_connect_for_snmp.customtaskmanager._get_all_schedules")
    def test_did_expiry_time_change_false(self, m_objects):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)

        mock_schedules(m_objects, {"expires": 120})
        self.assertFalse(task_manager.did_expiry_time_change(120, [WALK_TASK]))
        self.assertFalse(task_manager.did_expiry_time_change(120, [DISCOVERY_TASK]))

        mock_schedules(m_objects, {})
        self.assertFalse(task_manager.did_expiry_time_change(200, [WALK_TASK]))

        m_objects.return_value = []
        self.assertFalse(task_manager.did_expiry_time_change(200, [DISCOVERY_TASK]))

    @patch("redbeat.schedulers.RedBeatSchedulerEntry.from_key")
    @patch("splunk_connect_for_snmp.customtaskmanager.get_redis")
    def test_did_expiry_time_change_tolerates_orphan(self, m_get_redis, m_from_key):
        """
        Regression test for the historical crash: a meta-only orphan key
        among otherwise-healthy walk/poll/discovery entries used to abort
        the whole scan with KeyError: 'definition', so this method never
        got to delete anything. It must now skip the orphan and still
        delete exactly the entries whose expiry actually changed.
        """
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)
        m_get_redis.return_value.scan_iter.return_value = [
            "redbeat:sc4snmp;orphan;walk",
            "redbeat:sc4snmp;good;walk",
            "redbeat:sc4snmp;good;poll",
            "redbeat:sc4snmp;good;discovery",
        ]
        good_walk, good_poll, good_discovery = Mock(), Mock(), Mock()
        good_walk.task = WALK_TASK
        good_walk.options = {"expires": 120}
        good_poll.task = POLL_TASK
        good_poll.options = {"expires": 120}
        good_discovery.task = DISCOVERY_TASK
        good_discovery.options = {"expires": 300}

        def from_key_side_effect(key, app=None):
            if "orphan" in key:
                raise KeyError(key)
            return {
                "redbeat:sc4snmp;good;walk": good_walk,
                "redbeat:sc4snmp;good;poll": good_poll,
                "redbeat:sc4snmp;good;discovery": good_discovery,
            }[key]

        m_from_key.side_effect = from_key_side_effect

        with self.assertLogs(
            "splunk_connect_for_snmp.customtaskmanager", level="WARNING"
        ):
            did_time_change = task_manager.did_expiry_time_change(
                300, [WALK_TASK, POLL_TASK]
            )

        self.assertTrue(did_time_change)
        good_walk.delete.assert_called_once()
        good_poll.delete.assert_called_once()
        good_discovery.delete.assert_not_called()

    @patch("redbeat.schedulers.RedBeatSchedulerEntry.from_key")
    def test_walk_task_exists_true(self, redbeat_scheduler_entry_from_key):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)

        redbeat_scheduler_entry_from_key.return_value = Mock()

        self.assertTrue(task_manager.walk_task_exists("192.168.0.1:161"))
        redbeat_scheduler_entry_from_key.assert_called_with(
            "redbeat:sc4snmp;192.168.0.1:161;walk", app=ANY
        )

    @patch("redbeat.schedulers.RedBeatSchedulerEntry.from_key")
    def test_walk_task_exists_false(self, redbeat_scheduler_entry_from_key):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)

        redbeat_scheduler_entry_from_key.side_effect = KeyError

        self.assertFalse(task_manager.walk_task_exists("192.168.0.1:161"))
        redbeat_scheduler_entry_from_key.assert_called_with(
            "redbeat:sc4snmp;192.168.0.1:161;walk", app=ANY
        )

    @patch("splunk_connect_for_snmp.customtaskmanager._get_all_schedules")
    def test_rerun_all_walks(self, m_objects):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)

        task1 = Mock()
        task1.run_immediately = False
        task1.task = "splunk_connect_for_snmp.snmp.tasks.walk"
        task1.name = "test1"

        m_objects.return_value = [task1]

        task_manager.rerun_all_walks()

        task1.set_run_immediately.assert_called_with(True)
        task1.save.assert_called()

    @patch("redbeat.schedulers.RedBeatSchedulerEntry.from_key")
    @patch("splunk_connect_for_snmp.customtaskmanager.get_redis")
    def test_rerun_all_walks_skips_orphan(self, m_get_redis, m_from_key):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)
        m_get_redis.return_value.scan_iter.return_value = [
            "redbeat:sc4snmp;orphan;walk",
            "redbeat:sc4snmp;good;walk",
        ]
        good = Mock()
        good.task = WALK_TASK
        good.name = "sc4snmp;good;walk"

        def from_key_side_effect(key, app=None):
            if "orphan" in key:
                raise KeyError(key)
            return good

        m_from_key.side_effect = from_key_side_effect

        task_manager.rerun_all_walks()

        good.set_run_immediately.assert_called_with(True)
        good.save.assert_called()
