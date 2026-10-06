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
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor

from splunk_connect_for_snmp.common.common import close_mongo_client
from splunk_connect_for_snmp.common.customised_json_formatter import (
    CustomisedJSONFormatter,
)

formatter = CustomisedJSONFormatter()
HEARTBEAT_FILE = Path("/tmp/worker_heartbeat")
READINESS_FILE = Path("/tmp/worker_ready")


@signals.worker_process_init.connect(weak=False)
def init_celery_tracing(*args, **kwargs):
    CeleryInstrumentor().instrument()
    LoggingInstrumentor().instrument()


@signals.worker_before_create_process.connect(weak=False)
def close_parent_mongo_client(*args, **kwargs):
    # Runs in the prefork parent before each fork, so children don't inherit its sockets.
    close_mongo_client()


@signals.worker_process_init.connect(weak=False)
def rebind_mongo_clients(*args, **kwargs):
    # Task instances are built in the parent before fork; give each child its own client.
    for task in current_app.tasks.values():
        rebind = getattr(task, "rebind_mongo_client", None)
        if rebind is not None:
            rebind()


@signals.worker_process_shutdown.connect(weak=False)
def close_process_mongo_client(*args, **kwargs):
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
