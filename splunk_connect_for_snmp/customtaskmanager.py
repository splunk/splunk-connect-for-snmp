try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass
import logging
import os

from celerybeatmongo.models import PeriodicTask
from mongoengine import *
from mongoengine.connection import connect, disconnect
from typing import Union, List

logger = logging.getLogger(__name__)

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "sc4")
MONGO_DB_SCHEDULES = os.getenv("MONGO_DB_SCHEDULES", "schedules")


class CustomPeriodicTaskManage:
    def __init__(self):

        self.mongo_uri = MONGO_URI
        connect(host=self.mongo_uri, db=MONGO_DB)

    def __del__(self):
        disconnect()

    def delete_task(self, address: str):
        periodic = PeriodicTask.objects(target=address)
        for p in periodic:
            logger.debug(p)
            periodic_document = periodic.get(name=p.name)
            logger.debug("Got Schedule")
            periodic_document.delete()
            logger.debug("Deleting Schedule")

    def delete_unused_poll_tasks(self, target: str, activeschedules: List[str]):
        periodic = PeriodicTask.objects(target=target)
        for p in periodic:
            if not p.task == "splunk_connect_for_snmp.snmp.tasks.poll":
                continue
            logger.debug(p)
            periodic_document = periodic.get(name=p.name)
            logger.debug("Got Schedule")
            if not p.name in activeschedules:
                periodic_document.delete()
                logger.debug("Deleting Schedule")

    def enable_tasks(self, target):
        periodic = PeriodicTask.objects(target=target)
        for p in periodic:
            periodic_document = periodic.get(name=p.name)
            if not periodic_document.enabled:
                periodic_document.enabled = True
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
        return {
            "status": "success",
            "message": "{0} task has been managed and will be synced by celery beat service".format(
                task_data["task"]
            ),
        }
