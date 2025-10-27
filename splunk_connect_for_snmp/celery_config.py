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
# Support use of .env file for developers
from contextlib import suppress

from kombu import Queue

from splunk_connect_for_snmp.common.hummanbool import disable_mongo_logging, human_bool

with suppress(ImportError, OSError):
    from dotenv import load_dotenv

    load_dotenv()


import os

CELERY_TASK_TIMEOUT = int(os.getenv("CELERY_TASK_TIMEOUT", "2400"))
PREFETCH_COUNT = int(os.getenv("PREFETCH_COUNT", 1))

REDIS_MODE = os.getenv("REDIS_MODE", "standalone")

# Read components
REDIS_HOST = os.getenv("REDIS_HOST", "snmp-redis")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
REDIS_DB = os.getenv("REDIS_DB", "1")
CELERY_DB = os.getenv("CELERY_DB", "0")

# Sentinel-specific
REDIS_SENTINEL_SERVICE = os.getenv("REDIS_SENTINEL_SERVICE", "snmp-redis-sentinel")
REDIS_SENTINEL_PORT = os.getenv("REDIS_SENTINEL_PORT", "26379")
REDIS_MASTER_NAME = os.getenv("REDIS_MASTER_NAME", "mymaster")

# Construct URLs based on mode
if REDIS_MODE == "replication":
    # Sentinel mode
    if REDIS_PASSWORD:
        sentinel_base = f"sentinel://:{REDIS_PASSWORD}@{REDIS_SENTINEL_SERVICE}:{REDIS_SENTINEL_PORT}"
    else:
        sentinel_base = f"sentinel://{REDIS_SENTINEL_SERVICE}:{REDIS_SENTINEL_PORT}"

    redbeat_redis_url = f"{sentinel_base}/{REDIS_DB}"
    broker_url = f"{sentinel_base}/{CELERY_DB}"

    # Celery broker options for Sentinel
    broker_transport_options = {
        "master_name": REDIS_MASTER_NAME,
        "priority_steps": list(range(10)),
        "sep": ":",
        "queue_order_strategy": "priority",
    }
else:
    # Standalone mode (existing)
    if REDIS_PASSWORD:
        redis_base = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}"
    else:
        redis_base = f"redis://{REDIS_HOST}:{REDIS_PORT}"

    redbeat_redis_url = f"{redis_base}/{REDIS_DB}"
    broker_url = f"{redis_base}/{CELERY_DB}"

    broker_transport_options = {
        "priority_steps": list(range(10)),
        "sep": ":",
        "queue_order_strategy": "priority",
    }

# Fallback to env vars if set (backward compatibility)
redbeat_redis_url = os.getenv("REDIS_URL", redbeat_redis_url)
broker_url = os.getenv("CELERY_BROKER_URL", broker_url)

DISABLE_MONGO_DEBUG_LOGGING = human_bool(
    os.getenv("DISABLE_MONGO_DEBUG_LOGGING", "true")
)
result_extended = True
beat_scheduler = "redbeat.RedBeatScheduler"
redbeat_lock_key = None

if DISABLE_MONGO_DEBUG_LOGGING:
    disable_mongo_logging()

# Optimization for long running tasks
# https://docs.celeryproject.org/en/stable/userguide/optimizing.html#reserve-one-task-at-a-time
task_acks_late = True
worker_prefetch_multiplier = PREFETCH_COUNT
task_acks_on_failure_or_timeout = True
task_reject_on_worker_lost = True
task_time_limit = CELERY_TASK_TIMEOUT
task_create_missing_queues = False
task_ignore_result = True
result_persistent = False
result_expires = 60
task_default_priority = 5
task_default_queue = "poll"
broker_transport_options = {
    "priority_steps": list(range(10)),
    "sep": ":",
    "queue_order_strategy": "priority",
}
task_queues = (
    Queue("traps", exchange="traps"),
    Queue("poll", exchange="poll"),
    Queue("send", exchange="send"),
)
