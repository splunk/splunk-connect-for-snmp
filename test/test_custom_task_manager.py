from unittest import TestCase
from unittest.mock import patch, Mock

from splunk_connect_for_snmp.customtaskmanager import CustomPeriodicTaskManager


class TestCustomTaskManager(TestCase):

    @patch('celerybeatmongo.models.PeriodicTask.objects')
    def test_delete_unused_poll_tasks(self, m_objects):
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

        doc4 = Mock()
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

        self.assertEqual({'name': 'test1'}, calls[0].kwargs)
        self.assertEqual({'name': 'test2'}, calls[1].kwargs)
        self.assertEqual({'name': 'name1'}, calls[2].kwargs)

        doc1.delete.assert_called()
        doc2.delete.assert_called()
        doc3.delete.assert_not_called()
        doc4.delete.assert_not_called()

    @patch('celerybeatmongo.models.PeriodicTask.objects')
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

        self.assertEqual({'name': 'test1'}, calls[0].kwargs)
        self.assertEqual({'name': 'test2'}, calls[1].kwargs)
        self.assertEqual({'name': 'test3'}, calls[2].kwargs)
        self.assertEqual({'name': 'test4'}, calls[3].kwargs)

        doc1.delete.assert_called()
        doc2.delete.assert_called()
        doc3.delete.assert_called()
        doc4.delete.assert_called()

    @patch('celerybeatmongo.models.PeriodicTask.objects')
    def test_enable_tasks(self, m_objects):
        pass

    @patch('celerybeatmongo.models.PeriodicTask.objects')
    def test_disable_tasks(self, m_objects):
        pass

    @patch('celerybeatmongo.models.PeriodicTask.objects')
    def test_manage_task_new(self, m_objects):
        pass

    @patch('celerybeatmongo.models.PeriodicTask.objects')
    def test_manage_task_existing(self, m_objects):
        pass
