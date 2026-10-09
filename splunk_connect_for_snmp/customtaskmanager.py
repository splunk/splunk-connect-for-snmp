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
from typing import List, Set

from redbeat.schedulers import RedBeatSchedulerEntry

from .poller import app

logger = logging.getLogger(__name__)

WALK_TASK = "splunk_connect_for_snmp.snmp.tasks.walk"
POLL_TASK = "splunk_connect_for_snmp.snmp.tasks.poll"
DISCOVERY_TASK = "splunk_connect_for_snmp.discovery.tasks.discovery"

# RedBeatSchedulerEntry cannot be constructed without these. A partial
# definition (e.g. only name + run_immediately) can only update an entry that
# already exists, via the "existing task" branch below.
REQUIRED_NEW_TASK_FIELDS = ("name", "task", "schedule", "app")


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
            if periodic_document.task != "splunk_connect_for_snmp.snmp.tasks.poll":
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

    def delete_unused_discovery_tasks(self, active_schedules: List[str]):
        for periodic_document in RedBeatSchedulerEntry.get_schedules(app=app):
            if (
                periodic_document.task == DISCOVERY_TASK
                and periodic_document.name not in active_schedules
            ):
                periodic_document.delete()
                logger.info(
                    f"Deleting Schedule: {periodic_document.name} delete_unused_discovery_tasks"
                )

    def did_expiry_time_change(self, new_expiry_time, task_types: List[str]):
        expiry_times = self.get_chain_of_task_expiries(task_types)
        # manage_task never updates options, so a stale expiry is only fixed by recreating the tasks
        if not expiry_times or expiry_times == {new_expiry_time}:
            return False
        logger.debug(
            f"Expiry times {sorted(expiry_times)} of {task_types} differ from "
            f"configured {new_expiry_time}, recreating tasks"
        )
        for task_type in task_types:
            self.__delete_all_tasks_of_type(task_type, "did_expiry_time_change")
        return True

    def delete_all_poll_tasks(self):
        self.__delete_all_tasks_of_type(POLL_TASK, "delete_all_poll_tasks")

    def rerun_all_walks(self):
        periodic_tasks = RedBeatSchedulerEntry.get_schedules()
        for periodic_document in periodic_tasks:
            if periodic_document.task != "splunk_connect_for_snmp.snmp.tasks.walk":
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
            missing_fields = [
                field
                for field in REQUIRED_NEW_TASK_FIELDS
                if task_data.get(field) is None
            ]
            if missing_fields:
                logger.error(
                    f"Cannot set up a new task {task_name}: no definition "
                    f"exists for it in Redis, and the task_data provided to "
                    f"create one is missing {', '.join(missing_fields)}"
                )
                return
            logger.info(f"Setting up a new task: {task_name}")
            periodic_document = RedBeatSchedulerEntry(**task_data)
            periodic_document.save()
            if task_data.get("run_immediately"):
                periodic_document.reschedule()
            return
        periodic_document.save()

    def get_chain_of_task_expiries(self, task_types: List[str]) -> Set[int]:
        return {
            periodic_task.options["expires"]
            for periodic_task in RedBeatSchedulerEntry.get_schedules(app=app)
            if periodic_task.task in task_types
            and periodic_task.options.get("expires") is not None
        }

    def walk_task_exists(self, target: str) -> bool:
        walk_task_name = f"sc4snmp;{target};walk"
        try:
            RedBeatSchedulerEntry.from_key(f"redbeat:{walk_task_name}", app=app)
            return True
        except KeyError:
            return False
