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

from redbeat.schedulers import EntryPolicyChanged, RedBeatSchedulerEntry, get_redis

from .common import polling_jitter
from .common.polling_jitter import (
    INITIAL_REGISTRATION,
    SCHEDULE_CONTEXT,
    applied_settings,
    first_due,
    schedule_phase,
)
from .poller import app

logger = logging.getLogger(__name__)

WALK_TASK = "splunk_connect_for_snmp.snmp.tasks.walk"
POLL_TASK = "splunk_connect_for_snmp.snmp.tasks.poll"
DISCOVERY_TASK = "splunk_connect_for_snmp.discovery.tasks.discovery"

# Beat can change saved jitter settings while inventory prepares an update.
# Allow two reloads before reporting that the update could not be saved.
JITTER_POLICY_UPDATE_MAX_ATTEMPTS = 3

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

    def manage_task(
        self, *, initial_registration=False, inventory_update=False, **task_data
    ) -> None:
        """
        Create a missing recurring task or update one already saved.

        With jitter enabled, confirmed first registration adds an offset to a
        new WALK or POLL. Existing phased WALKs use their saved offset for
        inventory refreshes only while jitter remains enabled. Rebuilding a
        missing schedule keeps its usual recovery timing. Urgent requests stay
        due now.

        Phased entries keep their saved timing for definition-only updates.
        WALK and POLL creation refuses a schedule saved by another writer.
        Existing entries go to update_task(), which reloads changed policies
        and refuses deleted or replaced entries.

        :param initial_registration: Whether the caller confirmed first setup
        :param inventory_update: Whether changed inventory requested this WALK
        :param task_data: Full task definition or partial execution request

        :return: None
        :raises KeyError: If a loaded entry disappears or is replaced
        :raises PollingJitterError: If phased timing or identity is invalid
        :raises ValueError: If a numeric scheduling value is invalid
        :raises EntryPolicyChanged: If the policy keeps changing during update
        """
        task_name = task_data.get("name")
        try:
            periodic_document = RedBeatSchedulerEntry.from_key(
                f"redbeat:{task_name}", app=app
            )
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
            # Spread the first polling load for a new device. A missing schedule
            # for an existing device keeps its usual recovery timing.
            if initial_registration and polling_task and settings.enabled:
                self._save_initial_phase(periodic_document, settings)
                return
            if polling_task:
                # Two inventory workers can both see a missing schedule. Refuse
                # creation if another worker has already saved it.
                periodic_document.save_guarded(create=True)
            else:
                periodic_document.save()
            # Guarded creation already stores the initial timing and immediate
            # flag together. A second write could replace a newer schedule.
            if not polling_task and task_data.get("run_immediately"):
                periodic_document.reschedule()
            return

        self.update_task(
            periodic_document, task_data, inventory_update=inventory_update
        )

    def update_task(
        self,
        periodic_document: RedBeatSchedulerEntry,
        task_data: dict,
        *,
        inventory_update: bool = False,
    ) -> None:
        """
        Apply caller changes to an existing recurring task without creating one.

        For entries with applied jitter, definition-only changes keep stored
        timing and pending run requests. While jitter is enabled, an inventory
        WALK refresh requests now plus its saved offset. Restart WALKs and
        refreshes of existing POLLs above 300 seconds after a WALK remain
        urgent. Entries without an applied policy keep ordinary timing, with
        guarded writes for WALKs and POLLs.

        If Beat changes the applied policy during the write, reload the entry
        and reapply the caller's changes using that policy. Allow three total
        write attempts for this conflict only. Other errors pass to the caller.
        If the entry disappears during reload, do not recreate it.

        :param periodic_document: Existing recurring entry already loaded from Redis
        :param task_data: Fields or a partial run request including the entry name
        :param inventory_update: Whether changed inventory requested this WALK

        :return: None
        :raises KeyError: If the entry disappears or is replaced before saving
        :raises PollingJitterError: If the polling identity or timing is invalid
        :raises ValueError: If a numeric value or stored scheduling state is invalid
        :raises EntryPolicyChanged: If all three attempts encounter a policy change
        """
        task_name = task_data.get("name")
        entry_id = periodic_document.entry_id
        for attempt in range(JITTER_POLICY_UPDATE_MAX_ATTEMPTS):
            previous_schedule = periodic_document.schedule
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

            try:
                if periodic_document.jitter_fingerprint:
                    if (
                        inventory_update
                        and periodic_document.task == WALK_TASK
                        and polling_jitter.JITTER_SETTINGS.enabled
                    ):
                        # For example, settings now say 120s but this WALK still
                        # uses a 60s window. Refresh it using the saved 60s window
                        # until Beat applies the change to a following run.
                        settings = applied_settings(
                            periodic_document.jitter_fingerprint
                        )
                        _, offset, fingerprint = schedule_phase(
                            periodic_document, settings
                        )
                        periodic_document.request_run(
                            first_due(app.now().astimezone(timezone.utc), offset),
                            fingerprint=fingerprint,
                        )
                        return
                    if not task_data.get("run_immediately"):
                        # A POLL of 300 seconds or less can receive new profiles
                        # without running early. Keep its saved due time and any
                        # refresh already requested.
                        periodic_document.update_definition()
                        return
                    # Changing a WALK from 30 to 15 minutes changes its SHA-256
                    # input. Recalculate its marker with the same saved window.
                    # An unchanged interval uses None to keep the current marker.
                    request_fingerprint = None
                    if periodic_document.schedule != previous_schedule:
                        _, _, request_fingerprint = schedule_phase(
                            periodic_document,
                            applied_settings(periodic_document.jitter_fingerprint),
                        )
                    # Restart WALKs run now so recovery starts promptly. Existing
                    # POLLs above 300 seconds also run now after each WALK.
                    periodic_document.request_run(
                        app.now().astimezone(timezone.utc).replace(microsecond=0),
                        run_immediately=True,
                        fingerprint=request_fingerprint,
                    )
                    return
                if periodic_document.task in (WALK_TASK, POLL_TASK):
                    # Inventory may read an entry before Beat enables jitter on it.
                    # Do not let this older copy put the previous timing back.
                    periodic_document.save_guarded()
                else:
                    periodic_document.save()
                return
            except EntryPolicyChanged:
                # Beat enabled, disabled or changed jitter after this entry was
                # read. Reload it and apply this update using the saved policy.
                if attempt == JITTER_POLICY_UPDATE_MAX_ATTEMPTS - 1:
                    # Let the caller report this unsaved update after three conflicts.
                    raise
                periodic_document = RedBeatSchedulerEntry.from_key(
                    f"redbeat:{task_name}", app=app
                )
                # A device deleted and added again has a new schedule. Do not
                # apply the old inventory update to that replacement.
                if periodic_document.entry_id != entry_id:
                    raise KeyError(periodic_document.key)

    def _save_initial_phase(
        self, entry: RedBeatSchedulerEntry, settings: polling_jitter.JitterSettings
    ) -> None:
        """
        Save a new WALK or POLL with one offset and an unchanged interval.

        :param entry: New WALK or POLL entry that has not been saved
        :param settings: Validated jitter settings

        :return: None
        :raises PollingJitterError: If the polling identity or timing is invalid
        :raises ValueError: If a numeric scheduling value is invalid
        """
        seconds, offset, fingerprint = schedule_phase(entry, settings)
        task_type = "walk" if entry.task == WALK_TASK else "poll"
        baseline = entry.app.now().astimezone(timezone.utc)
        # A new 60s POLL already waits 60s, so add its offset after that wait.
        # WALKs and POLLs above 300s would start now, so they wait only the offset.
        if task_type == "poll" and seconds <= 300:
            baseline += entry.schedule.run_every
        # Mark the first outgoing WALK so profile setup also phases its new
        # POLLs. Later recurring WALKs omit this marker.
        first_run_kwargs = (
            {SCHEDULE_CONTEXT: INITIAL_REGISTRATION} if task_type == "walk" else {}
        )
        due = first_due(baseline, offset)
        # Redis and the interval check must agree on this first scheduled time.
        # Ordinary save() can choose a different time for a newly created entry.
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
