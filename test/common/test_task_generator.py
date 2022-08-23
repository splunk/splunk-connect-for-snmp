from unittest import TestCase
from unittest.mock import Mock

from celery.schedules import schedule

from splunk_connect_for_snmp.common.task_generator import (
    PollTaskGenerator,
    WalkTaskGenerator,
)


class TestTaskGenerator(TestCase):
    def test_walk_generator(self):
        app = Mock()
        walk_task_generator = WalkTaskGenerator(
            target="127.0.0.1", schedule_period=10, app=app, profile=None
        )
        generated_task = walk_task_generator.generate_task_definition()
        expected_task = {
            "app": app,
            "args": [],
            "enabled": True,
            "kwargs": {"address": "127.0.0.1", "profile": None},
            "name": "sc4snmp;127.0.0.1;walk",
            "options": WalkTaskGenerator.WALK_CHAIN_OF_TASKS,
            "run_immediately": True,
            "schedule": schedule(10),
            "target": "127.0.0.1",
            "task": "splunk_connect_for_snmp.snmp.tasks.walk",
        }
        self.assertEqual(generated_task, expected_task)

    def test_walk_generator_with_profile(self):
        app = Mock()
        walk_task_generator = WalkTaskGenerator(
            target="127.0.0.1", schedule_period=10, app=app, profile="walk1"
        )
        generated_task = walk_task_generator.generate_task_definition()
        expected_task = {
            "app": app,
            "args": [],
            "enabled": True,
            "kwargs": {"address": "127.0.0.1", "profile": "walk1"},
            "name": "sc4snmp;127.0.0.1;walk",
            "options": WalkTaskGenerator.WALK_CHAIN_OF_TASKS,
            "run_immediately": True,
            "schedule": schedule(10),
            "target": "127.0.0.1",
            "task": "splunk_connect_for_snmp.snmp.tasks.walk",
        }
        self.assertEqual(generated_task, expected_task)

    def test_poll_generator(self):
        app = Mock()
        poll_task_generator = PollTaskGenerator(
            target="127.0.0.1",
            schedule_period=10,
            app=app,
            profiles=["BaseProfile", "IFProfile"],
        )
        generated_task = poll_task_generator.generate_task_definition()
        expected_task = {
            "app": app,
            "args": [],
            "enabled": True,
            "kwargs": {
                "address": "127.0.0.1",
                "frequency": 10,
                "priority": 2,
                "profiles": ["BaseProfile", "IFProfile"],
            },
            "name": "sc4snmp;127.0.0.1;10;poll",
            "options": PollTaskGenerator.POLL_CHAIN_OF_TASKS,
            "run_immediately": False,
            "schedule": schedule(10),
            "target": "127.0.0.1",
            "task": "splunk_connect_for_snmp.snmp.tasks.poll",
        }
        self.assertEqual(generated_task, expected_task)

    def test_poll_generator_with_run_immediately(self):
        app = Mock()
        poll_task_generator = PollTaskGenerator(
            target="127.0.0.1",
            schedule_period=500,
            app=app,
            profiles=["BaseProfile", "IFProfile"],
        )
        generated_task = poll_task_generator.generate_task_definition()
        expected_task = {
            "app": app,
            "args": [],
            "enabled": True,
            "kwargs": {
                "address": "127.0.0.1",
                "frequency": 500,
                "priority": 2,
                "profiles": ["BaseProfile", "IFProfile"],
            },
            "name": "sc4snmp;127.0.0.1;500;poll",
            "options": PollTaskGenerator.POLL_CHAIN_OF_TASKS,
            "run_immediately": True,
            "schedule": schedule(500),
            "target": "127.0.0.1",
            "task": "splunk_connect_for_snmp.snmp.tasks.poll",
        }
        self.assertEqual(generated_task, expected_task)

    def test_global_variables(self):
        self.assertTrue(WalkTaskGenerator.WALK_CHAIN_OF_TASKS)
        self.assertTrue(PollTaskGenerator.POLL_CHAIN_OF_TASKS)
