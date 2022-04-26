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
from celery.schedules import schedule
import splunk_connect_for_snmp.celery_config

logger = logging.getLogger(__name__)


class CustomPeriodicTaskManager:
    def __init__(self):
        pass

    def __del__(self):
        pass

    def delete_unused_poll_tasks(self, target: str, activeschedules: List[str]):
        periodic_tasks = RedBeatSchedulerEntry.get_schedules_by_target(target, app=app)
        for periodic_document in periodic_tasks:
            if not periodic_document.task == "splunk_connect_for_snmp.snmp.tasks.poll":
                continue
            logger.debug("Got Schedule")
            if p.name not in activeschedules:
                if periodic_document.enabled:
                    periodic_document.enabled = False
                logger.debug(f"Deleting Schedule: {periodic_document.name}")

    def delete_all_poll_tasks(self):
        periodic_tasks = RedBeatSchedulerEntry.get_schedules()
        for periodic_document in periodic_tasks:
            if not periodic_document.task == "splunk_connect_for_snmp.snmp.tasks.poll":
                continue
            logger.debug("Got Schedule")
            periodic_document.delete()
            logger.debug("Deleting Schedule")

    def rerun_all_walks(self):
        periodic_tasks = RedBeatSchedulerEntry.get_schedules()
        for periodic_document in periodic_tasks:
            if not periodic_document.task == "splunk_connect_for_snmp.snmp.tasks.walk":
                continue
            periodic_document.run_immediately = True
            logger.debug("Got Schedule")
            periodic_document.save()
            periodic_document.reschedule()

    def delete_disabled_poll_tasks(self):
        periodic_tasks = RedBeatSchedulerEntry.get_schedules()
        for periodic_document in periodic_tasks:
            periodic_document.delete()
            logger.debug("Deleting Schedule")

    def enable_tasks(self, target):
        periodic_tasks = RedBeatSchedulerEntry.get_schedules_by_target(target["target"], app=app)
        for periodic_document in periodic_tasks:
            if not periodic_document.enabled:
                periodic_document.enabled = True
            periodic_document.save()
            periodic_document.reschedule()

    def disable_tasks(self, target):
        periodic_tasks = RedBeatSchedulerEntry.get_schedules_by_target(target["target"], app=app)
        for periodic_document in periodic_tasks:
            if periodic_document.enabled:
                periodic_document.enabled = False
            periodic_document.save()
            periodic_document.reschedule()

    def manage_task(self, run_immediately_if_new: bool = False, **task_data) -> None:
        try:
            periodic = RedBeatSchedulerEntry.from_key(f"redbeat:{task_data['name']}", app=app)
        except KeyError:
            periodic = None
        if periodic:
            logger.debug("Existing Schedule")
            isChanged = False
            periodic_document = periodic
            for key, value in task_data.items():
                if key == "schedule":
                    if not periodic_document.schedule == task_data["schedule"]:
                        periodic_document.schedule = task_data["schedule"]
                        isChanged = True
                elif key == "target":
                    pass
                else:
                    if key in periodic_document:
                        if not periodic_document[key] == task_data[key]:
                            periodic_document[key] = task_data[key]
                            isChanged = True
                    else:
                        periodic_document[key] = task_data[key]
                        isChanged = True

        else:
            logger.debug("New Schedule")
            isChanged = True
            periodic_document = RedBeatSchedulerEntry(**task_data)
            if "target" in task_data:
                periodic_document.target = task_data["target"]
            if "options" in task_data:
                periodic_document.options = task_data["options"]

        if isChanged:
            periodic_document.save()
            periodic_document.reschedule()
