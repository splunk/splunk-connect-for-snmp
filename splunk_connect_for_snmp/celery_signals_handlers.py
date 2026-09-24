#
# Copyright 2023 Splunk Inc.
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

from pathlib import Path

from celery import Celery, current_app, signals
from celery.utils.log import get_task_logger
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor

from splunk_connect_for_snmp.common.customised_json_formatter import (
    CustomisedJSONFormatter,
)
from splunk_connect_for_snmp.common.mongo_client import close_mongo_client

logger = get_task_logger(__name__)
formatter = CustomisedJSONFormatter()
HEARTBEAT_FILE = Path("/tmp/worker_heartbeat")
READINESS_FILE = Path("/tmp/worker_ready")


@signals.worker_process_init.connect(weak=False)
def init_celery_tracing(*args, **kwargs):
    CeleryInstrumentor().instrument()
    LoggingInstrumentor().instrument()


@signals.worker_process_init.connect(weak=False)
def init_worker_mongo_clients(*args, **kwargs):
    """Eagerly run each Poller-based task's Mongo/MIB bootstrap right after fork.

    This pins the MIB-index fetch to worker-startup time, matching the
    documented "restart the worker to pick up a new MIB" behavior: a purely
    reactive task like trap otherwise wouldn't run its bootstrap until its
    first real message arrives, which can be arbitrarily later than the
    worker actually starting up. before_start still calls
    _ensure_worker_initialized() on every task run; the guard flag on each
    task instance makes that a no-op once this has already succeeded here,
    and acts as a lazy retry - visible through normal task-failure handling -
    if this eager attempt failed (e.g. Mongo/mibserver unreachable at
    startup, an exception here is logged and swallowed by Celery's signal
    dispatcher rather than failing the worker).
    """
    for task in current_app.tasks.values():
        ensure_initialized = getattr(task, "_ensure_worker_initialized", None)
        if ensure_initialized is None:
            continue
        try:
            ensure_initialized()
        except Exception:
            logger.exception(
                f"Eager worker-startup bootstrap failed for task {task.name!r}; "
                "will retry on its first real task execution"
            )


@signals.worker_process_shutdown.connect(weak=False)
def close_worker_mongo_client(*args, **kwargs):
    close_mongo_client()


@signals.beat_init.connect(weak=False)
def init_celery_beat_tracing(*args, **kwargs):
    CeleryInstrumentor().instrument()
    LoggingInstrumentor().instrument()


@signals.after_setup_task_logger.connect
def setup_task_logger(logger, *args, **kwargs):
    for handler in logger.handlers:
        handler.setFormatter(formatter)


@signals.heartbeat_sent.connect
def liveness_indicator(**_):
    HEARTBEAT_FILE.touch()


@signals.worker_ready.connect
def readiness_indicator(sender=None, **_):
    READINESS_FILE.touch()
    if sender is not None:
        try:
            queue_names = {q.name for q in sender.task_consumer.queues}
        except AttributeError:
            queue_names = set()
        if "traps" in queue_names:
            from splunk_connect_for_snmp.snmp.trap_varbind_limit import (
                log_trap_varbind_limit_config,
            )

            log_trap_varbind_limit_config()


@signals.worker_shutdown.connect
def worker_shutdown(**_):
    for f in (HEARTBEAT_FILE, READINESS_FILE):
        f.unlink()
