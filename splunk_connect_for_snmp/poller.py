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

from splunk_connect_for_snmp.common.customised_json_formatter import (
    CustomisedJSONFormatter,
)

with suppress(ImportError):
    from dotenv import load_dotenv

    load_dotenv()

import os

from celery import Celery, signals
from celery.utils.log import get_task_logger
from opentelemetry import trace
# from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.trace import TracerProvider
# from opentelemetry.sdk.trace.export import BatchSpanProcessor

provider = TracerProvider()
# processor = BatchSpanProcessor(JaegerExporter())
# provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
formatter = CustomisedJSONFormatter()

logger = get_task_logger(__name__)

# //using rabbitmq as the message broker
app = Celery("sc4snmp_poller")
app.config_from_object("splunk_connect_for_snmp.celery_config")
# app.conf.update(**config)

INVENTORY_PATH = os.getenv("INVENTORY_PATH", "/app/inventory/inventory.csv")
INVENTORY_REFRESH_RATE = int(os.getenv("INVENTORY_REFRESH_RATE", "600"))


@signals.worker_process_init.connect(weak=False)
def init_celery_tracing(*args, **kwargs):
    CeleryInstrumentor().instrument()
    LoggingInstrumentor().instrument()


@signals.beat_init.connect(weak=False)
def init_celery_beat_tracing(*args, **kwargs):
    CeleryInstrumentor().instrument()
    LoggingInstrumentor().instrument()


@signals.after_setup_task_logger.connect
def setup_task_logger(logger, *args, **kwargs):
    for handler in logger.handlers:
        handler.setFormatter(formatter)


app.autodiscover_tasks(
    packages=[
        "splunk_connect_for_snmp",
        "splunk_connect_for_snmp.enrich",
        "splunk_connect_for_snmp.inventory",
        "splunk_connect_for_snmp.snmp",
        "splunk_connect_for_snmp.splunk",
    ]
)
