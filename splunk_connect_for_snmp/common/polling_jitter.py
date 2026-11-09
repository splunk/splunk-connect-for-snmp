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
import hashlib
import ipaddress
import os
import unicodedata
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta

from splunk_connect_for_snmp.common.common import human_bool, positive_integer


class PollingJitterError(ValueError):
    """Raised when polling jitter settings or scheduling values are invalid."""


with suppress(ImportError, OSError):
    from dotenv import load_dotenv

    load_dotenv()

# Changing these environment values takes effect when this process restarts.
POLLING_JITTER_ENABLED = human_bool(os.getenv("POLLING_JITTER_ENABLED", "false"))
# Ignore the configured window while jitter is disabled. Beat still reads each
# saved policy so it can align the run after the one already scheduled.
POLLING_JITTER_WINDOW_SECONDS = 60
if POLLING_JITTER_ENABLED:
    POLLING_JITTER_WINDOW_SECONDS = positive_integer(
        os.getenv("POLLING_JITTER_WINDOW_SECONDS", "60"),
        "POLLING_JITTER_WINDOW_SECONDS",
        86400,
    )
INITIAL_REGISTRATION = "initial_registration"
SCHEDULE_CONTEXT = "_schedule_context"


@dataclass(frozen=True)
class JitterSettings:
    """Store whether jitter is enabled and the window for offset calculation."""

    enabled: bool = False
    window_seconds: int = 60


JITTER_SETTINGS = JitterSettings(POLLING_JITTER_ENABLED, POLLING_JITTER_WINDOW_SECONDS)


def applied_settings(fingerprint: str) -> JitterSettings:
    """
    Read the policy already applied to a managed schedule.

    While jitter is enabled, an inventory refresh uses this saved window even
    if the configured window has changed. Beat applies a new window to the run
    following its next reservation.

    :param fingerprint: Saved algorithm, configured window and identity digest

    :return: Settings for the saved policy
    :raises PollingJitterError: If the saved policy is invalid or unsupported
    """
    try:
        algorithm, window, digest = fingerprint.split(":")
        if (
            algorithm != "sha256-v1"
            or len(digest) != 64
            or len(bytes.fromhex(digest)) != 32
        ):
            raise ValueError("Invalid applied policy")
        return JitterSettings(True, positive_integer(window, "Jitter window", 86400))
    except ValueError as error:
        raise PollingJitterError("Invalid applied polling jitter policy") from error


def canonical_identity(
    address: str, port: int | str, interval: int | str, task_type: str
) -> str:
    """
    Build the stable identity used to choose a schedule's jitter offset.

    IP addresses use standard formatting and hostnames are trimmed and
    case-folded without a DNS lookup. This does not change schedule keys.

    :param address: Device IP address or hostname, without a port
    :param port: Device SNMP port
    :param interval: Polling interval in whole seconds
    :param task_type: Either walk or poll

    :return: Canonical identity containing no credentials or profile names
    :raises PollingJitterError: If the address or task type is invalid
    :raises ValueError: If the port or interval is invalid
    """
    # An address must not add extra fields or hide characters in the text
    # used to calculate its offset.
    if (
        not isinstance(address, str)
        or "|" in address
        or any(unicodedata.category(char).startswith("C") for char in address)
    ):
        raise PollingJitterError("Invalid jitter device address")
    address = address.strip()
    if not address or any(char.isspace() for char in address):
        raise PollingJitterError("Invalid jitter device address")
    try:
        address = str(ipaddress.ip_address(address))
    except ValueError:
        if ":" in address:
            raise PollingJitterError("Invalid jitter device address") from None
        address = address.casefold()
    if task_type not in ("walk", "poll"):
        raise PollingJitterError("Jitter task type must be walk or poll")
    port = positive_integer(port, "SNMP port", 65535)
    interval = positive_integer(interval, "Polling interval")
    # Changing a password or profile name must not change the offset. Use only
    # the device address, port, interval and whether this is a WALK or POLL.
    return f"v1|{task_type}|{address}|{port}|{interval}"


def calculate_offset(
    address: str,
    port: int | str,
    interval: int | str,
    task_type: str,
    settings: JitterSettings,
) -> tuple[int, str]:
    """
    Choose a repeatable positive offset for one recurring schedule.

    The offset is between one second and the smaller of the configured window
    and this schedule's interval. The same identity and window always give the
    same offset. Different identities may share an offset.

    :param address: Device IP address or hostname
    :param port: Device SNMP port
    :param interval: Schedule interval in whole seconds
    :param task_type: Either walk or poll
    :param settings: Validated jitter settings

    :return: Offset in seconds and the applied-policy fingerprint
    :raises PollingJitterError: If the address or task type is invalid
    :raises ValueError: If the port or interval is invalid
    """
    identity = canonical_identity(address, port, interval, task_type)
    interval = int(interval)
    digest = hashlib.sha256(identity.encode("utf-8")).digest()
    offset = 1 + int.from_bytes(digest, "big") % min(settings.window_seconds, interval)
    # Save the requested window so Beat can notice a later settings change,
    # even when this schedule's interval kept its offset range smaller.
    return offset, f"sha256-v1:{settings.window_seconds}:{digest.hex()}"


def first_due(baseline: datetime, offset: int) -> datetime:
    """
    Add one offset while retaining the baseline's microseconds.

    Used for initial scheduling, an inventory refresh or a later policy change.
    Callers provide a UTC baseline and the calculated positive offset.

    :param baseline: Due time before the offset, as an aware UTC timestamp
    :param offset: Positive whole-second offset

    :return: Baseline plus exactly the offset, retaining microseconds
    """
    return baseline + timedelta(seconds=offset)


def schedule_phase(entry, settings: JitterSettings) -> tuple[int, int, str]:
    """
    Calculate an offset from a recurring WALK or POLL definition.

    The address is split at its last colon so IPv6 addresses stay intact.
    Profile names and credentials are not part of the calculation.

    :param entry: Recurring polling entry
    :param settings: Window to apply to this entry

    :return: Interval seconds, positive offset and policy fingerprint
    :raises PollingJitterError: If the polling definition cannot be phased
    :raises ValueError: If a numeric identity value is invalid
    """
    interval = entry.schedule.run_every
    if interval.microseconds:
        raise PollingJitterError("Polling jitter requires a whole-second interval")
    seconds = interval.days * 86400 + interval.seconds
    target = entry.kwargs.get("address")
    if not isinstance(target, str) or ":" not in target:
        raise PollingJitterError("Polling jitter requires a device address with a port")
    # IPv6 addresses contain colons too. Only the final colon separates the port.
    address, port = target.rsplit(":", 1)
    task_type = "walk" if entry.task.endswith(".walk") else "poll"
    offset, fingerprint = calculate_offset(address, port, seconds, task_type, settings)
    return seconds, offset, fingerprint
