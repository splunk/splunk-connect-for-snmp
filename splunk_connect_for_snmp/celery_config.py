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
REDIS_MASTER_NAME = os.getenv("REDIS_MASTER_NAME", "snmp-redis")
REDIS_SENTINEL_SERVICE = os.getenv("REDIS_SENTINEL_SERVICE", "snmp-redis-sentinel")
REDIS_SENTINEL_REPLICAS = int(os.getenv("REDIS_SENTINEL_REPLICAS", "3"))
NAMESPACE = os.getenv("NAMESPACE", "sc4snmp")

# Construct URLs based on mode
if REDIS_MODE == "replication":
    # Celery broker options for Sentinel
    broker_transport_options = {
        "service_name": "mymaster",
        "master_name": "mymaster",
        "priority_steps": list(range(10)),
        "retry_on_timeout": True,
        "socket_timeout": 5,
        "retry_policy": {
            'max_retries': 100,
            'interval_start': 0,
            'interval_step': 2,
            'interval_max': 5,
        },
        "sep": ":",
        "db": 1,
        "queue_order_strategy": "priority",
        "sentinels": [(REDIS_SENTINEL_SERVICE, 26379)],
        "password": os.getenv("REDIS_PASSWORD", None)
    }
else:
    broker_transport_options = {
        "priority_steps": list(range(10)),
        "sep": ":",
        "queue_order_strategy": "priority",
    }

# Should be set by ./construct-redis-url.sh script
redbeat_redis_url = os.getenv("REDIS_URL")
broker_url = os.getenv("CELERY_BROKER_URL")

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
task_queues = (
    Queue("traps", exchange="traps"),
    Queue("poll", exchange="poll"),
    Queue("send", exchange="send"),
)
