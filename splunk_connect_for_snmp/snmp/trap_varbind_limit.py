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
import os
from typing import Optional

logger = logging.getLogger(__name__)

TRAP_VARBIND_DECODE_MIN = 1
TRAP_VARBIND_DECODE_MAX = 500
TRAP_VARBIND_DECODE_DEFAULT = 250
_ENV_MAX_TRAP_VARBINDS_TO_DECODE = "MAX_TRAP_VARBINDS_TO_DECODE"


def parse_max_trap_varbinds_to_decode(
    raw: str | None = None,
    *,
    minimum: int = TRAP_VARBIND_DECODE_MIN,
    maximum: int = TRAP_VARBIND_DECODE_MAX,
    default: int = TRAP_VARBIND_DECODE_DEFAULT,
) -> int:
    """Parse and clamp MAX_TRAP_VARBINDS_TO_DECODE (invalid values use default)."""
    if raw is None:
        raw = os.getenv(_ENV_MAX_TRAP_VARBINDS_TO_DECODE, str(default))
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        logger.warning(
            "Invalid %s=%r; using default %d (allowed range %d-%d)",
            _ENV_MAX_TRAP_VARBINDS_TO_DECODE,
            raw,
            default,
            minimum,
            maximum,
        )
        value = default
    if value < minimum:
        logger.warning(
            "%s=%d is below minimum %d; using %d",
            _ENV_MAX_TRAP_VARBINDS_TO_DECODE,
            value,
            minimum,
            minimum,
        )
        return minimum
    if value > maximum:
        logger.warning(
            "%s=%d exceeds maximum %d; using %d",
            _ENV_MAX_TRAP_VARBINDS_TO_DECODE,
            value,
            maximum,
            maximum,
        )
        return maximum
    return value


MAX_TRAP_VARBINDS_TO_DECODE = parse_max_trap_varbinds_to_decode()

_limit_config_logged = False


def log_trap_varbind_limit_config(log: Optional[logging.Logger] = None) -> None:
    """Log the effective varbind decode limit once per process."""
    global _limit_config_logged
    if _limit_config_logged:
        return
    _limit_config_logged = True
    active = log or logger
    active.info(
        "Trap varbind decode limit: %s=%d (allowed range %d-%d)",
        _ENV_MAX_TRAP_VARBINDS_TO_DECODE,
        MAX_TRAP_VARBINDS_TO_DECODE,
        TRAP_VARBIND_DECODE_MIN,
        TRAP_VARBIND_DECODE_MAX,
    )


def limit_trap_varbind_pairs(
    varbind_pairs, *, log: Optional[logging.Logger] = None, source=None
):
    """Return at most MAX_TRAP_VARBINDS_TO_DECODE varbind (name, value) pairs."""
    active = log or logger
    limit = MAX_TRAP_VARBINDS_TO_DECODE
    pairs = list(varbind_pairs)
    if len(pairs) <= limit:
        return pairs
    dropped = len(pairs) - limit
    origin = source if source is not None else "unknown"
    active.info(
        "Trap from %s has %d varbinds; decoding first %d (%d dropped, %s=%d)",
        origin,
        len(pairs),
        limit,
        dropped,
        _ENV_MAX_TRAP_VARBINDS_TO_DECODE,
        limit,
    )
    return pairs[:limit]
