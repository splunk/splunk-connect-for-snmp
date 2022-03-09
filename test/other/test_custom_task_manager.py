from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch

from splunk_connect_for_snmp.customtaskmanager import CustomPeriodicTaskManager


class TestCustomTaskManager(TestCase):
    @patch("celerybeatmongo.models.PeriodicTask.objects")
    def test_delete_unused_poll_tasks(self, m_objects):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)
        doc1 = Mock()
        doc1.enabled = True
        task1 = Mock()
        task1.task = "splunk_connect_for_snmp.snmp.tasks.poll"
        task1.name = "test1"

        doc2 = Mock()
        doc2.enabled = True
        task2 = Mock()
        task2.task = "splunk_connect_for_snmp.snmp.tasks.poll"
        task2.name = "test2"

        doc3 = Mock()
        doc3.enabled = True
        task3 = Mock()
        task3.task = "splunk_connect_for_snmp.snmp.tasks.walk"
        task3.name = "test3"

        doc4 = Mock()
        doc4.enabled = True
        task4 = Mock()
        task4.task = "splunk_connect_for_snmp.snmp.tasks.poll"
        task4.name = "name1"

        periodic_list = Mock()
        periodic_list.__iter__ = Mock(return_value=iter([task1, task2, task3, task4]))
        periodic_list.get.side_effect = [doc1, doc2, doc3, doc4]

        m_objects.return_value = periodic_list

        task_manager.delete_unused_poll_tasks("192.168.0.1", ["name1", "name2"])

        m_objects.assert_called_with(target="192.168.0.1")
        calls = periodic_list.get.call_args_list

        self.assertEqual({"name": "test1"}, calls[0].kwargs)
        self.assertEqual({"name": "test2"}, calls[1].kwargs)
        self.assertEqual({"name": "name1"}, calls[2].kwargs)

        self.assertFalse(doc1.enabled)
        self.assertFalse(doc2.enabled)
        self.assertTrue(doc3.enabled)
        self.assertTrue(doc4.enabled)

    @patch("celerybeatmongo.models.PeriodicTask.objects")
    def test_delete_disabled_poll_tasks(self, m_objects):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)

        doc1 = Mock()
        task1 = Mock()
        task1.name = "test1"

        doc2 = Mock()
        task2 = Mock()
        task2.name = "test2"

        doc3 = Mock()
        task3 = Mock()
        task3.name = "test3"

        doc4 = Mock()
        task4 = Mock()
        task4.name = "test4"

        periodic_list = Mock()
        periodic_list.__iter__ = Mock(return_value=iter([task1, task2, task3, task4]))
        periodic_list.get.side_effect = [doc1, doc2, doc3, doc4]

        m_objects.return_value = periodic_list

        task_manager.delete_disabled_poll_tasks()

        m_objects.assert_called_with(enabled=False)
        calls = periodic_list.get.call_args_list

        self.assertEqual({"name": "test1"}, calls[0].kwargs)
        self.assertEqual({"name": "test2"}, calls[1].kwargs)
        self.assertEqual({"name": "test3"}, calls[2].kwargs)
        self.assertEqual({"name": "test4"}, calls[3].kwargs)

        doc1.delete.assert_called()
        doc2.delete.assert_called()
        doc3.delete.assert_called()
        doc4.delete.assert_called()

    @patch("celerybeatmongo.models.PeriodicTask.objects")
    def test_enable_tasks(self, m_objects):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)

        doc1 = Mock()
        doc1.enabled = False
        task1 = Mock()
        task1.name = "test1"

        doc2 = Mock()
        doc2.enabled = False
        task2 = Mock()
        task2.name = "test2"

        periodic_list = Mock()
        periodic_list.__iter__ = Mock(return_value=iter([task1, task2]))
        periodic_list.get.side_effect = [doc1, doc2]
        m_objects.return_value = periodic_list

        task_manager.enable_tasks("192.168.0.1")

        m_objects.assert_called_with(target="192.168.0.1")

        calls = periodic_list.get.call_args_list

        self.assertEqual({"name": "test1"}, calls[0].kwargs)
        self.assertEqual({"name": "test2"}, calls[1].kwargs)

        self.assertTrue(doc1.enabled)
        self.assertTrue(doc2.enabled)

        doc1.save.assert_called()
        doc2.save.assert_called()

    @patch("celerybeatmongo.models.PeriodicTask.objects")
    def test_disable_tasks(self, m_objects):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)

        doc1 = Mock()
        doc1.enabled = True
        task1 = Mock()
        task1.name = "test1"

        doc2 = Mock()
        doc2.enabled = True
        task2 = Mock()
        task2.name = "test2"

        periodic_list = Mock()
        periodic_list.__iter__ = Mock(return_value=iter([task1, task2]))
        periodic_list.get.side_effect = [doc1, doc2]
        m_objects.return_value = periodic_list

        task_manager.disable_tasks("192.168.0.1")

        m_objects.assert_called_with(target="192.168.0.1")

        calls = periodic_list.get.call_args_list

        self.assertEqual({"name": "test1"}, calls[0].kwargs)
        self.assertEqual({"name": "test2"}, calls[1].kwargs)

        self.assertFalse(doc1.enabled)
        self.assertFalse(doc2.enabled)

        doc1.save.assert_called()
        doc2.save.assert_called()

    @patch("celerybeatmongo.models.PeriodicTask.objects")
    def test_manage_task_existing_interval(self, m_objects):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)

        task1 = Mock()
        task1.name = "test1"
        doc1 = MagicMock()

        m_objects.return_value = task1
        task1.get.return_value = doc1

        d = {"name": "test1"}
        doc1.__getitem__.side_effect = d.__getitem__
        doc1.__setitem__.side_effect = d.__setitem__
        doc1.__contains__.side_effect = d.__contains__

        task_data = {"name": "test1", "interval": {"every": 60, "period": "seconds"}}

        task_manager.manage_task(**task_data)

        m_objects.assert_called_with(name="test1")
        task1.get.assert_called_with(name="test1")

        self.assertEqual({"name": "test1"}, d)

        self.assertEqual(60, doc1.interval.every)
        self.assertEqual("seconds", doc1.interval.period)
        doc1.save.assert_called_with()

    @patch("celerybeatmongo.models.PeriodicTask.objects")
    def test_manage_task_existing_crontab(self, m_objects):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)

        task1 = Mock()
        task1.name = "test1"
        doc1 = MagicMock()

        m_objects.return_value = task1
        task1.get.return_value = doc1

        d = {"name": "test1"}
        doc1.__getitem__.side_effect = d.__getitem__
        doc1.__setitem__.side_effect = d.__setitem__
        doc1.__contains__.side_effect = d.__contains__

        task_data = {"name": "test1", "crontab": {"minute": 30, "hour": 10}}

        task_manager.manage_task(**task_data)

        m_objects.assert_called_with(name="test1")
        task1.get.assert_called_with(name="test1")

        self.assertEqual({"name": "test1"}, d)

        self.assertEqual("30 10 * * * (m/h/d/dM/MY)", str(doc1.crontab))
        doc1.save.assert_called_with()

    @patch("celerybeatmongo.models.PeriodicTask.objects")
    def test_manage_task_existing_target(self, m_objects):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)

        task1 = Mock()
        task1.name = "test1"
        doc1 = MagicMock()

        m_objects.return_value = task1
        task1.get.return_value = doc1

        d = {"name": "test1"}
        doc1.__getitem__.side_effect = d.__getitem__
        doc1.__setitem__.side_effect = d.__setitem__
        doc1.__contains__.side_effect = d.__contains__

        task_data = {"name": "test1", "target": "192.168.0.1"}

        task_manager.manage_task(**task_data)

        self.assertEqual({"name": "test1"}, d)

        m_objects.assert_called_with(name="test1")
        task1.get.assert_called_with(name="test1")

        doc1.save.assert_not_called()

    @patch("celerybeatmongo.models.PeriodicTask.objects")
    def test_manage_task_existing_only_props(self, m_objects):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)

        task1 = Mock()
        task1.name = "test1"
        doc1 = MagicMock()

        m_objects.return_value = task1
        task1.get.return_value = doc1

        d = {"name": "test1"}
        doc1.__getitem__.side_effect = d.__getitem__
        doc1.__setitem__.side_effect = d.__setitem__
        doc1.__contains__.side_effect = d.__contains__

        task_data = {"name": "test1", "prop1": "value1", "prop2": "value2"}

        task_manager.manage_task(**task_data)

        self.assertEqual({"name": "test1", "prop1": "value1", "prop2": "value2"}, d)

        m_objects.assert_called_with(name="test1")
        task1.get.assert_called_with(name="test1")

        doc1.save.assert_called()

    @patch("celerybeatmongo.models.PeriodicTask.objects")
    def test_delete_all_poll_tasks(self, m_objects):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)
        doc1 = Mock()
        task1 = Mock()
        task1.task = "splunk_connect_for_snmp.snmp.tasks.poll"
        task1.name = "test1"

        doc2 = Mock()
        task2 = Mock()
        task2.task = "splunk_connect_for_snmp.snmp.tasks.poll"
        task2.name = "test2"

        doc3 = Mock()
        task3 = Mock()
        task3.task = "splunk_connect_for_snmp.snmp.tasks.walk"
        task3.name = "test3"

        periodic_list = Mock()
        periodic_list.__iter__ = Mock(return_value=iter([task1, task2, task3]))
        periodic_list.get.side_effect = [doc1, doc2, doc3]

        m_objects.return_value = periodic_list

        task_manager.delete_all_poll_tasks()

        calls = periodic_list.get.call_args_list

        self.assertEqual({"name": "test1"}, calls[0].kwargs)
        self.assertEqual({"name": "test2"}, calls[1].kwargs)

        doc1.delete.assert_called()
        doc2.delete.assert_called()
        doc3.delete.assert_not_called()

    @patch("celerybeatmongo.models.PeriodicTask.objects")
    def test_rerun_all_walks(self, m_objects):
        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)

        doc1 = Mock()
        doc1.run_immediately = False
        task1 = Mock()
        task1.task = "splunk_connect_for_snmp.snmp.tasks.walk"
        task1.name = "test1"

        periodic_list = Mock()
        periodic_list.__iter__ = Mock(return_value=iter([task1]))
        periodic_list.get.side_effect = [doc1]

        m_objects.return_value = periodic_list

        task_manager.rerun_all_walks()

        calls = periodic_list.get.call_args_list

        self.assertEqual({"name": "test1"}, calls[0].kwargs)

        self.assertTrue(doc1.run_immediately)
        doc1.save.assert_called()

    @patch("celerybeatmongo.models.PeriodicTask.objects")
    @patch("celerybeatmongo.models.PeriodicTask.save")
    def test_manage_task_new(self, m_save, m_objects):
        m_objects.return_value = None

        task_manager = CustomPeriodicTaskManager.__new__(CustomPeriodicTaskManager)
        m_objects.return_value = None
        task_data = {
            "task": "task1",
            "name": "test1",
            "args": {"arg1": "val1", "arg2": "val2"},
            "kwargs": {"karg1": "val1", "karg2": "val2"},
            "interval": {"every": 60, "period": "seconds"},
            "target": "some_target",
            "options": "some+option",
            "enabled": True,
        }

        task_manager.manage_task(**task_data)

        m_save.assert_called()
