from celery import Celery, chain, group, signature
from celery.schedules import schedule


class TaskGenerator:
    def __init__(self, target: str, schedule_period: int, app: Celery, host_group=None):
        self.target = target
        self.schedule_period = schedule_period
        self.app = app
        self.group = host_group

    def generate_task_definition(self):
        task_definition = {
            "target": self.target,
            "args": [],
            "kwargs": {"address": self.target},
            "schedule": schedule(self.schedule_period),
            "enabled": True,
            "app": self.app,
        }
        if self.group:
            task_definition["kwargs"]["group"] = self.group
        return task_definition


class WalkTaskGenerator(TaskGenerator):

    WALK_CHAIN_OF_TASKS = {
        "link": chain(
            signature("splunk_connect_for_snmp.enrich.tasks.enrich")
            .set(queue="poll")
            .set(priority=4),
            group(
                signature(
                    "splunk_connect_for_snmp.inventory.tasks.inventory_setup_poller"
                )
                .set(queue="poll")
                .set(priority=3),
                chain(
                    signature("splunk_connect_for_snmp.splunk.tasks.prepare")
                    .set(queue="send")
                    .set(priority=1),
                    signature("splunk_connect_for_snmp.splunk.tasks.send")
                    .set(queue="send")
                    .set(priority=0),
                ),
            ),
        ),
    }

    def __init__(self, target, schedule_period, app, host_group, profile):
        super().__init__(target, schedule_period, app, host_group)
        self.profile = profile

    def generate_task_definition(self):
        task_data = super().generate_task_definition()
        name = f"sc4snmp;{self.target};walk"
        task_data["name"] = name
        task_data["task"] = "splunk_connect_for_snmp.snmp.tasks.walk"
        task_data["options"] = self.WALK_CHAIN_OF_TASKS
        task_data["run_immediately"] = True
        walk_kwargs = {"profile": self.profile}
        task_data["kwargs"].update(walk_kwargs)
        return task_data


class PollTaskGenerator(TaskGenerator):

    POLL_CHAIN_OF_TASKS = {
        "link": chain(
            signature("splunk_connect_for_snmp.enrich.tasks.enrich")
            .set(queue="poll")
            .set(priority=4),
            chain(
                signature("splunk_connect_for_snmp.splunk.tasks.prepare")
                .set(queue="send")
                .set(priority=1),
                signature("splunk_connect_for_snmp.splunk.tasks.send")
                .set(queue="send")
                .set(priority=0),
            ),
        ),
    }

    def __init__(self, target, schedule_period, app, host_group, profiles):
        super().__init__(target, schedule_period, app, host_group)
        self.profiles = profiles

    def generate_task_definition(self):
        task_data = super().generate_task_definition()
        task_data["name"] = f"sc4snmp;{self.target};{self.schedule_period};poll"
        task_data["task"] = "splunk_connect_for_snmp.snmp.tasks.poll"
        task_data["options"] = self.POLL_CHAIN_OF_TASKS
        task_data["run_immediately"] = self.run_immediately
        poll_kwargs = {
            "profiles": list(self.profiles),
            "frequency": self.schedule_period,
            "priority": 2,
        }
        task_data["kwargs"].update(poll_kwargs)
        return task_data

    @property
    def run_immediately(self):
        if self.schedule_period > 300:
            return True
        return False
