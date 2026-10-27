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
from datetime import timezone
from typing import List, Set

from redbeat.schedulers import RedBeatSchedulerEntry, get_redis

from .common import polling_jitter
from .common.polling_jitter import (
    INITIAL_REGISTRATION,
    SCHEDULE_CONTEXT,
    PollingJitterError,
    calculate_offset,
    first_due,
)
from .poller import app

logger = logging.getLogger(__name__)

WALK_TASK = "splunk_connect_for_snmp.snmp.tasks.walk"
POLL_TASK = "splunk_connect_for_snmp.snmp.tasks.poll"
DISCOVERY_TASK = "splunk_connect_for_snmp.discovery.tasks.discovery"

# RedBeatSchedulerEntry cannot be constructed without these. A partial
# definition (e.g. only name + run_immediately) can only update an entry that
# already exists, via the "existing task" branch below.
REQUIRED_NEW_TASK_FIELDS = ("name", "task", "schedule", "app")


def _load_schedules(match: str) -> List[RedBeatSchedulerEntry]:
    # Per-key safe replacement for RedBeatSchedulerEntry.get_schedules()/
    # get_schedules_by_target(), which abort the whole scan with a raw
    # KeyError on the first key missing a "definition" field (e.g. a
    # meta-only orphan hash). from_key raises a clean KeyError for such a
    # key instead, so only that key is skipped.
    schedules = []
    for key in get_redis(app).scan_iter(match):
        try:
            schedules.append(RedBeatSchedulerEntry.from_key(key, app=app))
        except KeyError:
            logger.warning(f"Skipping schedule {key}: no definition stored in Redis")
        except ValueError as e:
            logger.warning(f"Skipping schedule {key}: invalid JSON ({e})")
    return schedules


def _get_all_schedules() -> List[RedBeatSchedulerEntry]:
    return _load_schedules("redbeat:sc4snmp;*")


def _get_schedules_by_target(target: str) -> List[RedBeatSchedulerEntry]:
    return _load_schedules(f"*{target};*")


class CustomPeriodicTaskManager:
    def __delete_all_tasks_of_type(self, task, function_name):
        periodic_tasks = _get_all_schedules()
        for periodic_document in periodic_tasks:
            if periodic_document.task != task:
                continue
            periodic_document.delete()
            logger.debug(f"Deleting Schedule {periodic_document.name} {function_name}")

    def delete_unused_poll_tasks(self, target: str, activeschedules: List[str]):
        periodic_tasks = _get_schedules_by_target(target)
        for periodic_document in periodic_tasks:
            if periodic_document.task != "splunk_connect_for_snmp.snmp.tasks.poll":
                continue
            logger.debug(f"Got Schedule: {periodic_document.name}")
            if periodic_document.name not in activeschedules:
                periodic_document.delete()
                logger.debug(
                    f"Deleting Schedule: {periodic_document.name} delete_unused_poll_tasks"
                )

    def delete_unused_discovery_tasks(self, active_schedules: List[str]):
        for periodic_document in _get_all_schedules():
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
        periodic_tasks = _get_all_schedules()
        for periodic_document in periodic_tasks:
            if periodic_document.task != "splunk_connect_for_snmp.snmp.tasks.walk":
                continue
            periodic_document.set_run_immediately(True)
            if periodic_document.jitter_fingerprint:
                periodic_document.first_run_kwargs = {}
            logger.debug("Got Schedule")
            periodic_document.save()
            periodic_document.reschedule()

    def delete_all_tasks_of_host(self, target):
        RedBeatSchedulerEntry.delete_schedules_by_target(target, app=app)

    def manage_task(self, *, initial_registration=False, **task_data) -> None:
        """
        Create or update the existing recurring entry for one polling task.

        Only confirmed initial registration may phase a new WALK or POLL.
        Existing execution requests keep their current behavior in this stage.
        A managed definition-only update preserves its saved due time.

        :param initial_registration: Whether the caller confirmed first setup
        :param task_data: Existing task definition or partial execution request

        :return: None
        :raises PollingJitterError: If phased timing or identity is invalid
        :raises ValueError: If a numeric scheduling value is invalid
        """
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
            settings = polling_jitter.JITTER_SETTINGS
            polling_task = task_data.get("task") in (WALK_TASK, POLL_TASK)
            if initial_registration and polling_task and settings.enabled:
                self._save_initial_phase(periodic_document, settings)
                return
            periodic_document.save()
            if task_data.get("run_immediately"):
                periodic_document.reschedule()
            return
        if periodic_document.jitter_fingerprint:
            if not task_data.get("run_immediately"):
                periodic_document.update_definition()
                return
            periodic_document.first_run_kwargs = {}
        periodic_document.save()

    def _save_initial_phase(
        self, entry: RedBeatSchedulerEntry, settings: polling_jitter.JitterSettings
    ) -> None:
        """
        Save a new device schedule using its normal baseline plus one offset.

        The WALK/POLL generators supply an interval schedule and address string.
        The target key is split at its last colon, preserving an IPv6 address.
        The resulting identity is validated without changing the schedule key.
        After saving, a debug message records the offset and selected first due
        without including credentials or the task payload.

        :param entry: New WALK or POLL entry that has not been saved
        :param settings: Validated jitter settings

        :return: None
        :raises PollingJitterError: If the target or interval cannot be phased
        :raises ValueError: If a numeric scheduling value is invalid
        """
        interval = entry.schedule.run_every
        if interval.microseconds:
            raise PollingJitterError("Jitter requires a whole-second polling interval")
        seconds = interval.days * 86400 + interval.seconds
        target = entry.kwargs.get("address")
        if ":" not in target:
            raise PollingJitterError(
                "Jitter requires a device address and explicit port"
            )
        address, port = target.rsplit(":", 1)
        task_type = "walk" if entry.task == WALK_TASK else "poll"
        # Profile validation also accepts whole-number floats and MongoDB integers.
        # Compare values without rewriting the payload or schedule key.
        if task_type == "poll" and entry.kwargs.get("frequency") != seconds:
            raise PollingJitterError("POLL frequency must match its schedule interval")
        offset, fingerprint = calculate_offset(
            address, port, seconds, task_type, settings
        )
        baseline = entry.app.now().astimezone(timezone.utc)
        if task_type == "poll" and seconds <= 300:
            baseline += interval
        first_run_kwargs = (
            {SCHEDULE_CONTEXT: INITIAL_REGISTRATION} if task_type == "walk" else {}
        )
        due = first_due(baseline, offset)
        entry.save_with_first_due(due, fingerprint, first_run_kwargs=first_run_kwargs)
        logger.debug(
            f"Applied polling jitter: schedule={entry.name} interval_seconds={seconds} "
            f"window_seconds={settings.window_seconds} "
            f"effective_window_seconds={min(settings.window_seconds, seconds)} "
            f"offset_seconds={offset} first_due_utc={due.isoformat()}"
        )

    def get_chain_of_task_expiries(self, task_types: List[str]) -> Set[int]:
        return {
            periodic_task.options["expires"]
            for periodic_task in _get_all_schedules()
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
