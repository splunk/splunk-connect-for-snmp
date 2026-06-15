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

TRAP_VARBIND_DECODE_MIN = 0
TRAP_VARBIND_DECODE_DEFAULT = 0
_ENV_MAX_TRAP_VARBINDS_TO_DECODE = "MAX_TRAP_VARBINDS_TO_DECODE"


def parse_max_trap_varbinds_to_decode(
    raw: str | None = None,
    *,
    minimum: int = TRAP_VARBIND_DECODE_MIN,
    default: int = TRAP_VARBIND_DECODE_DEFAULT,
) -> int:
    """Parse MAX_TRAP_VARBINDS_TO_DECODE; 0 means unlimited (decode all varbinds)."""
    if raw is None:
        raw = os.getenv(_ENV_MAX_TRAP_VARBINDS_TO_DECODE, str(default))
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        logger.warning(
            "Invalid %s=%r; using default %d (0=unlimited)",
            _ENV_MAX_TRAP_VARBINDS_TO_DECODE,
            raw,
            default,
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
    limit = MAX_TRAP_VARBINDS_TO_DECODE
    if limit == 0:
        active.info(
            "Trap varbind decode limit: %s=0 (unlimited)",
            _ENV_MAX_TRAP_VARBINDS_TO_DECODE,
        )
    else:
        active.info(
            "Trap varbind decode limit: %s=%d",
            _ENV_MAX_TRAP_VARBINDS_TO_DECODE,
            limit,
        )


def limit_trap_varbind_pairs(
    varbind_pairs, *, log: Optional[logging.Logger] = None, source=None
):
    """Return varbind pairs, truncating when MAX_TRAP_VARBINDS_TO_DECODE > 0."""
    active = log or logger
    limit = MAX_TRAP_VARBINDS_TO_DECODE
    pairs = list(varbind_pairs)
    if limit == 0 or len(pairs) <= limit:
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
