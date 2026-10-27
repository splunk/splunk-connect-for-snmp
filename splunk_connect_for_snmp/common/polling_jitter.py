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
from datetime import datetime, timedelta, timezone

from splunk_connect_for_snmp.common.common import human_bool, positive_integer


class PollingJitterError(ValueError):
    """Raised when polling jitter settings or scheduling values are invalid."""


with suppress(ImportError, OSError):
    from dotenv import load_dotenv

    load_dotenv()

POLLING_JITTER_ENABLED = human_bool(os.getenv("POLLING_JITTER_ENABLED", "false"))
POLLING_JITTER_WINDOW_SECONDS = positive_integer(
    os.getenv("POLLING_JITTER_WINDOW_SECONDS", "60"),
    "POLLING_JITTER_WINDOW_SECONDS",
    86400,
)
INITIAL_REGISTRATION = "initial_registration"
SCHEDULE_CONTEXT = "_schedule_context"


@dataclass(frozen=True)
class JitterSettings:
    """Store the enabled flag and window used to calculate an initial offset."""

    enabled: bool = False
    window_seconds: int = 60


JITTER_SETTINGS = JitterSettings(POLLING_JITTER_ENABLED, POLLING_JITTER_WINDOW_SECONDS)


def canonical_identity(
    address: str, port: int | str, interval: int | str, task_type: str
) -> str:
    """
    Build the stable identity used to choose a schedule's starting offset.

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

    The window is capped for this schedule only. The same identity always
    gives the same offset under the same settings. Different identities may
    share an offset.

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
    interval = int(interval)  # canonical_identity already validated this value.
    digest = hashlib.sha256(identity.encode("utf-8")).digest()
    offset = 1 + int.from_bytes(digest, "big") % min(settings.window_seconds, interval)
    return offset, f"sha256-v1:{settings.window_seconds}:{digest.hex()}"


def first_due(baseline: datetime, offset: int) -> datetime:
    """
    Add one offset and round the due time upward to a whole UTC second.

    :param baseline: Existing first-run baseline as an aware UTC timestamp
    :param offset: Positive whole-second offset

    :return: Due time that is never earlier than baseline plus offset
    :raises PollingJitterError: If the baseline is not UTC
    :raises ValueError: If the offset is invalid
    """
    if baseline.utcoffset() != timedelta(0):
        raise PollingJitterError("Jitter baseline must be an aware UTC timestamp")
    due = baseline + timedelta(seconds=positive_integer(offset, "Jitter offset"))
    if due.microsecond:
        due += timedelta(seconds=1)
        due = due.replace(microsecond=0)
    return due.astimezone(timezone.utc)
