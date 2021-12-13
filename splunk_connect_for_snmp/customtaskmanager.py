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

from celerybeatmongo.models import PeriodicTask
from mongoengine.connection import connect, disconnect

import splunk_connect_for_snmp.celery_config

logger = logging.getLogger(__name__)


class CustomPeriodicTaskManager:
    def __init__(self):
        connect(
            host=splunk_connect_for_snmp.celery_config.mongodb_scheduler_url,
            db=splunk_connect_for_snmp.celery_config.mongodb_scheduler_db,
        )

    def __del__(self):
        disconnect()

    def delete_unused_poll_tasks(self, target: str, activeschedules: List[str]):
        periodic = PeriodicTask.objects(target=target)
        for p in periodic:
            if not p.task == "splunk_connect_for_snmp.snmp.tasks.poll":
                continue
            logger.debug(p)
            periodic_document = periodic.get(name=p.name)
            logger.debug("Got Schedule")
            if p.name not in activeschedules:
                periodic_document.delete()
                logger.debug("Deleting Schedule")

    def enable_tasks(self, target):
        periodic = PeriodicTask.objects(target=target)
        for p in periodic:
            periodic_document = periodic.get(name=p.name)
            if not periodic_document.enabled:
                periodic_document.enabled = True
            periodic_document.save()

    def disable_tasks(self, target):
        periodic = PeriodicTask.objects(target=target)
        for p in periodic:
            periodic_document = periodic.get(name=p.name)
            if periodic_document.enabled:
                periodic_document.enabled = False
            periodic_document.save()

    def manage_task(self, run_immediately_if_new: bool = False, **task_data) -> None:
        periodic = PeriodicTask.objects(name=task_data["name"])
        if periodic:
            logger.debug("Existing Schedule")
            isChanged = False
            periodic_document = periodic.get(name=task_data["name"])
            for key, value in task_data.items():
                if key == "interval":
                    if not periodic_document.interval == PeriodicTask.Interval(
                            **task_data["interval"]
                    ):
                        periodic_document.interval = PeriodicTask.Interval(
                            **task_data["interval"]
                        )
                        isChanged = True
                elif key == "crontab":
                    if not periodic_document.crontab == PeriodicTask.Interval(
                            **task_data["crontab"]
                    ):
                        periodic_document.crontab = PeriodicTask.Interval(
                            **task_data["crontab"]
                        )
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

        else:
            logger.debug("New Schedule")
            isChanged = True
            periodic_document = PeriodicTask(task=task_data["task"])
            periodic_document.name = task_data["name"]
            periodic_document.args = task_data["args"]
            periodic_document.kwargs = task_data["kwargs"]
            if "interval" in task_data:
                periodic_document.interval = PeriodicTask.Interval(
                    **task_data["interval"]
                )
            else:
                periodic_document.crontab = PeriodicTask.Crontab(**task_data["crontab"])
            periodic_document.enabled = task_data["enabled"]
            periodic_document.run_immediately = task_data.get(
                "run_immediately", run_immediately_if_new
            )
            if "target" in task_data:
                periodic_document["target"] = task_data["target"]
            if "options" in task_data:
                periodic_document["options"] = task_data["options"]

        if isChanged:
            periodic_document.save()
