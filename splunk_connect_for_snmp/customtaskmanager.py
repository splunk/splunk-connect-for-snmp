#
# Copyright 2021 Splunk Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import logging
from typing import List

from redbeat.schedulers import RedBeatSchedulerEntry

from .poller import app

logger = logging.getLogger(__name__)


class CustomPeriodicTaskManager:
    def __delete_all_tasks_of_type(self, task, function_name):
        periodic_tasks = RedBeatSchedulerEntry.get_schedules()
        for periodic_document in periodic_tasks:
            if periodic_document.task != task:
                continue
            logger.debug(f"Got Schedule: {periodic_document.name}")
            periodic_document = RedBeatSchedulerEntry.from_key(
                f"redbeat:{periodic_document.name}", app=app
            )
            periodic_document.delete()
            logger.debug(f"Deleting Schedule {periodic_document.name} {function_name}")

    def delete_unused_poll_tasks(self, target: str, activeschedules: List[str]):
        periodic_tasks = RedBeatSchedulerEntry.get_schedules_by_target(target, app=app)
        for periodic_document in periodic_tasks:
            if not periodic_document.task == "splunk_connect_for_snmp.snmp.tasks.poll":
                continue
            logger.debug(f"Got Schedule: {periodic_document.name}")
            periodic_document = RedBeatSchedulerEntry.from_key(
                f"redbeat:{periodic_document.name}", app=app
            )
            if periodic_document.name not in activeschedules:
                periodic_document.delete()
                logger.debug(
                    f"Deleting Schedule: {periodic_document.name} delete_unused_poll_tasks"
                )

    def did_expiry_time_change(self, new_expiry_time):
        previous_expiry_time = self.get_chain_of_task_expiry()
        expiry_time_changed = False
        if previous_expiry_time is not None and previous_expiry_time != new_expiry_time:
            self.delete_all_walk_tasks()
            self.delete_all_poll_tasks()
            expiry_time_changed = True
        return expiry_time_changed

    def delete_all_poll_tasks(self):
        self.__delete_all_tasks_of_type(
            "splunk_connect_for_snmp.snmp.tasks.poll", "delete_all_poll_tasks"
        )

    def delete_all_walk_tasks(self):
        self.__delete_all_tasks_of_type(
            "splunk_connect_for_snmp.snmp.tasks.walk", "delete_all_walk_tasks"
        )

    def rerun_all_walks(self):
        periodic_tasks = RedBeatSchedulerEntry.get_schedules()
        for periodic_document in periodic_tasks:
            if not periodic_document.task == "splunk_connect_for_snmp.snmp.tasks.walk":
                continue
            periodic_document = RedBeatSchedulerEntry.from_key(
                f"redbeat:{periodic_document.name}", app=app
            )
            periodic_document.set_run_immediately(True)
            logger.debug("Got Schedule")
            periodic_document.save()
            periodic_document.reschedule()

    def delete_all_tasks_of_host(self, target):
        RedBeatSchedulerEntry.delete_schedules_by_target(target, app=app)

    def manage_task(self, **task_data) -> None:
        task_name = task_data.get("name")
        # When task is updated, we don't want to change existing schedules.
        # If task interval is very long, running walk process in between would result in calculating
        # next execution again.
        try:
            periodic_document = RedBeatSchedulerEntry.from_key(
                f"redbeat:{task_name}", app=app
            )
            args_list = [
                "target",
                "args",
                "kwargs",
                "run_immediately",
                "schedule",
                "enabled",
            ]
            update_log = f"Updated task: {task_name}. Updated arguments: "
            logger.info(f"Updating a task: {task_name}")
            for arg in args_list:
                if arg in task_data:
                    update_log += f"{arg}={task_data.get(arg)}  |  "
                    setattr(periodic_document, arg, task_data.get(arg))
            logger.info(update_log)
        except KeyError:
            logger.info(f"Setting up a new task: {task_name}")
            periodic_document = RedBeatSchedulerEntry(**task_data)
        periodic_document.save()

    def get_chain_of_task_expiry(self):
        periodic_tasks = RedBeatSchedulerEntry.get_schedules(app=app)
        if periodic_tasks:
            return periodic_tasks[0].options.get("expires", None)
        else:
            return None
