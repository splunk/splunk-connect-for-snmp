from celery import Celery, signals
from celery.utils.log import get_task_logger
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from splunk_connect_for_snmp import customtaskmanager

provider = TracerProvider()
processor = BatchSpanProcessor(JaegerExporter())
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

logger = get_task_logger(__name__)

# //using rabbitmq as the message broker
app = Celery("sc4snmp_poller")
app.config_from_object("splunk_connect_for_snmp.celery_config")
# app.conf.update(**config)


@signals.worker_process_init.connect(weak=False)
def init_celery_tracing(*args, **kwargs):
    CeleryInstrumentor().instrument()
    LoggingInstrumentor().instrument()


@signals.beat_init.connect(weak=False)
def init_celery_beat_tracing(*args, **kwargs):
    CeleryInstrumentor().instrument()
    LoggingInstrumentor().instrument()


app.autodiscover_tasks(
    packages=[
        "splunk_connect_for_snmp",
        "splunk_connect_for_snmp.enrich",
        "splunk_connect_for_snmp.inventory",
        "splunk_connect_for_snmp.snmp",
        "splunk_connect_for_snmp.splunk",
    ]
)


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs) -> None:
    periodic_obj = customtaskmanager.CustomPeriodicTaskManage()

    schedule_data_create_interval = {
        "name": "sc4snmp;inventory;seed",
        "task": "splunk_connect_for_snmp.inventory.tasks.inventory_seed",
        "args": [],
        "kwargs": {"path": "inventory.csv"},
        "interval": {"every": 600, "period": "seconds"},
        "enabled": True,
        "run_immediately": True,
    }

    periodic_obj.manage_task(**schedule_data_create_interval)
