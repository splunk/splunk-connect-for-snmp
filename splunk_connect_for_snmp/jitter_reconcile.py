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
from datetime import datetime, timezone

from splunk_connect_for_snmp.common import polling_jitter
from splunk_connect_for_snmp.common.polling_jitter import (
    applied_settings,
    effective_window_seconds,
    first_due,
    schedule_phase,
)

logger = logging.getLogger(__name__)
POLLING_TASKS = (
    "splunk_connect_for_snmp.snmp.tasks.walk",
    "splunk_connect_for_snmp.snmp.tasks.poll",
)


def apply_entry_policy(entry):
    """
    Calculate the due time after the run Beat is currently reserving.

    RedBeat saves the result with the current reservation. Settings changes
    adjust the following run once. The selected run keeps its stored timing,
    including when jitter is disabled. Matching saved settings skip hashing
    and keep normal intervals. This function returns a proposal without
    writing schedule state.

    :param entry: Recurring entry representing the reservation being saved

    :return: Following due time and fingerprint, or None for no policy change.
        A pair with a None due changes only the fingerprint
    """
    if entry.task not in POLLING_TASKS or not entry._strtobool(entry.enabled):
        return None
    # The setting may now say 120 seconds while this schedule still uses 60.
    # Compare the requested window with the one saved on this schedule.
    settings = polling_jitter.JITTER_SETTINGS
    fingerprint = entry.jitter_fingerprint
    if not settings.enabled and not fingerprint:
        return None

    previous = applied_settings(fingerprint) if fingerprint else None
    # This schedule already uses the requested window. Keep its normal interval
    # instead of adding the same offset again on every run.
    if (
        previous
        and settings.enabled
        and previous.window_seconds == settings.window_seconds
    ):
        return None

    interval = entry.schedule.run_every
    # The current run has already been selected, including any inventory refresh
    # or urgent recovery. Apply settings after its normal next interval.
    baseline = entry.last_run_at.astimezone(timezone.utc) + interval
    if not settings.enabled:
        # Removing jitter only needs the interval, not another device hash.
        offset = 0
        requested_fingerprint = None
        # After disabling jitter, move the following run to the nearest shared
        # UTC interval boundary. A tie goes later. This one gap may be shorter
        # or longer before the normal interval resumes.
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        quotient, remainder = divmod(baseline - epoch, interval)
        if remainder * 2 >= interval:
            quotient += 1
        due = epoch + quotient * interval
    else:
        seconds, offset, requested_fingerprint = schedule_phase(entry, settings)
        if previous and effective_window_seconds(
            previous, seconds
        ) == effective_window_seconds(settings, seconds):
            # A 60-second POLL keeps its 1-59-second range when the window
            # grows from 60 to 120. Save the setting without moving its next run.
            due = None
        else:
            # Add the new offset once after this reservation plus one interval.
            # Later runs keep normal intervals from this new due time.
            due = first_due(baseline, offset)

    logger.debug(
        f"Calculated following polling timing: schedule={entry.name} "
        f"enabled={settings.enabled} window_seconds={settings.window_seconds} "
        f"effective_window_seconds={effective_window_seconds(settings, int(interval.total_seconds()))} "
        f"offset_seconds={offset} "
        f"due_utc={due.isoformat() if due else 'unchanged'}"
    )
    # Remove the marker on disable so later reservations keep normal intervals.
    return due, requested_fingerprint
