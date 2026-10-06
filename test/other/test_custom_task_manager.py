from unittest import TestCase
from unittest.mock import ANY, MagicMock, Mock, patch

from celery.schedules import schedule

from splunk_connect_for_snmp.customtaskmanager import (
    DISCOVERY_TASK,
    POLL_TASK,
    WALK_TASK,
    CustomPeriodicTaskManager,
)


def raise_exception():
    raise KeyError


def mock_schedules(m_from_key, m_get_schedules, options, options_by_type=None):
    options_by_type = options_by_type or {}
    schedules = []
    from_key_entries = {}
    for task_type in (WALK_TASK, POLL_TASK, DISCOVERY_TASK):
        schedule_entry = Mock()
        schedule_entry.task = task_type
        schedule_entry.name = f"sc4snmp;{task_type}"
        schedule_entry.options = options_by_type.get(task_type, options)
        schedules.append(schedule_entry)
        from_key_entries[task_type] = Mock()
    m_get_schedules.return_value = schedules
    m_from_key.side_effect = lambda key, app=None: from_key_entries[
        key.removeprefix("redbeat:sc4snmp;")
    ]
    return from_key_entries


class TestCustomTaskManager(TestCase):
    @patch("redbeat.schedulers.RedBeatSchedulerEntry.get_schedules_by_target")
    @patch("redbeat.schedulers.RedBeatSchedulerEntry.from_key")
    def test_delete_unused_poll_tasks(self, m_from_key, m_objects):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)
        doc1 = Mock()
        doc1.enabled = True
        task1 = Mock()
        task1.delete = Mock()
        task1.task = "splunk_connect_for_snmp.snmp.tasks.poll"
        task1.name = "test1"

        doc2 = Mock()
        doc2.enabled = True
        task2 = Mock()
        task2.delete = Mock()
        task2.task = "splunk_connect_for_snmp.snmp.tasks.poll"
        task2.name = "test2"

        doc3 = Mock()
        doc3.enabled = True
        task3 = Mock()
        task3.delete = Mock()
        task3.task = "splunk_connect_for_snmp.snmp.tasks.walk"
        task3.name = "test3"

        doc4 = Mock()
        doc4.enabled = True
        task4 = Mock()
        task4.task = "splunk_connect_for_snmp.snmp.tasks.poll"
        task4.name = "name1"

        periodic_list = Mock()
        periodic_list.__iter__ = Mock(return_value=iter([task1, task2, task3, task4]))

        m_objects.return_value = periodic_list
        m_from_key.side_effect = [task1, task2, task4]

        task_manager.delete_unused_poll_tasks("192.168.0.1", ["name1", "name2"])
        m_objects.assert_called_with("192.168.0.1", app=ANY)
        self.assertTrue(task1.delete.called)
        self.assertTrue(task2.delete.called)
        self.assertFalse(task3.delete.called)
        self.assertFalse(task4.delete.called)

    @patch("redbeat.schedulers.RedBeatSchedulerEntry.get_schedules")
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
        }

        redbeat_scheduler.return_value = task1
        task_manager.manage_task(**task_data)

        redbeat_scheduler_entry_from_key.assert_called_with("redbeat:test1", app=ANY)

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

    @patch("redbeat.schedulers.RedBeatSchedulerEntry.get_schedules")
    @patch("redbeat.schedulers.RedBeatSchedulerEntry.from_key")
    def test_delete_all_poll_tasks(self, m_from_key, m_objects):
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

        periodic_list = [task1, task2, task3]

        m_objects.return_value = periodic_list
        task_from_key1, task_from_key2, task_from_key3 = Mock(), Mock(), Mock()
        m_from_key.side_effect = [task_from_key1, task_from_key2, task_from_key3]
        task_manager.delete_all_poll_tasks()
        self.assertTrue(task_from_key1.delete.called)
        self.assertTrue(task_from_key2.delete.called)
        self.assertFalse(task_from_key3.delete.called)

    @patch("redbeat.schedulers.RedBeatSchedulerEntry.get_schedules")
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

    @patch("redbeat.schedulers.RedBeatSchedulerEntry.get_schedules")
    @patch("redbeat.schedulers.RedBeatSchedulerEntry.from_key")
    def test_did_expiry_time_change_deletes_only_polling_tasks(
        self, m_from_key, m_objects
    ):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)
        entries = mock_schedules(m_from_key, m_objects, {"expires": 120})

        did_time_change = task_manager.did_expiry_time_change(
            300, [WALK_TASK, POLL_TASK]
        )

        self.assertTrue(did_time_change)
        entries[WALK_TASK].delete.assert_called_once()
        entries[POLL_TASK].delete.assert_called_once()
        entries[DISCOVERY_TASK].delete.assert_not_called()

    @patch("redbeat.schedulers.RedBeatSchedulerEntry.get_schedules")
    @patch("redbeat.schedulers.RedBeatSchedulerEntry.from_key")
    def test_did_expiry_time_change_deletes_only_discovery_tasks(
        self, m_from_key, m_objects
    ):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)
        entries = mock_schedules(m_from_key, m_objects, {"expires": 120})

        did_time_change = task_manager.did_expiry_time_change(300, [DISCOVERY_TASK])

        self.assertTrue(did_time_change)
        entries[DISCOVERY_TASK].delete.assert_called_once()
        entries[WALK_TASK].delete.assert_not_called()
        entries[POLL_TASK].delete.assert_not_called()

    @patch("redbeat.schedulers.RedBeatSchedulerEntry.get_schedules")
    @patch("redbeat.schedulers.RedBeatSchedulerEntry.from_key")
    def test_did_expiry_time_change_mixed_expiry_times(self, m_from_key, m_objects):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)
        mixed = {WALK_TASK: {"expires": 300}, POLL_TASK: {"expires": 60}}

        for configured_expiry in (300, 60):
            with self.subTest(configured_expiry=configured_expiry):
                entries = mock_schedules(
                    m_from_key, m_objects, {"expires": 300}, options_by_type=mixed
                )

                did_time_change = task_manager.did_expiry_time_change(
                    configured_expiry, [WALK_TASK, POLL_TASK]
                )

                self.assertTrue(did_time_change)
                entries[WALK_TASK].delete.assert_called_once()
                entries[POLL_TASK].delete.assert_called_once()
                entries[DISCOVERY_TASK].delete.assert_not_called()

    @patch("redbeat.schedulers.RedBeatSchedulerEntry.get_schedules")
    @patch("redbeat.schedulers.RedBeatSchedulerEntry.from_key")
    def test_did_expiry_time_change_false(self, m_from_key, m_objects):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)

        mock_schedules(m_from_key, m_objects, {"expires": 120})
        self.assertFalse(task_manager.did_expiry_time_change(120, [WALK_TASK]))
        self.assertFalse(task_manager.did_expiry_time_change(120, [DISCOVERY_TASK]))

        mock_schedules(m_from_key, m_objects, {})
        self.assertFalse(task_manager.did_expiry_time_change(200, [WALK_TASK]))

        m_objects.return_value = []
        self.assertFalse(task_manager.did_expiry_time_change(200, [DISCOVERY_TASK]))

        m_from_key.assert_not_called()

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

    @patch("redbeat.schedulers.RedBeatSchedulerEntry.get_schedules")
    @patch("redbeat.schedulers.RedBeatSchedulerEntry.from_key")
    def test_rerun_all_walks(self, m_from_key, m_objects):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)

        task1 = Mock()
        task1.run_immediately = False
        task1.task = "splunk_connect_for_snmp.snmp.tasks.walk"
        task1.name = "test1"

        task_from_key1 = Mock()
        m_objects.return_value = [task1]
        m_from_key.return_value = task_from_key1

        task_manager.rerun_all_walks()

        task_from_key1.set_run_immediately.assert_called_with(True)
        task_from_key1.save.assert_called()
