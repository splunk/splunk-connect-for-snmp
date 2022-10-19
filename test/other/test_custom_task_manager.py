from unittest import TestCase
from unittest.mock import ANY, MagicMock, Mock, patch

from celery.schedules import schedule

from splunk_connect_for_snmp.customtaskmanager import CustomPeriodicTaskManager


def raise_exception():
    raise KeyError


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
