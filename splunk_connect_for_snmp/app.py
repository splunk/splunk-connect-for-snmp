# Support use of .env file for developers
try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass

import os

import pymongo
from celery import Celery, signals
from celery.utils.log import get_task_logger
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

provider = TracerProvider()
processor = BatchSpanProcessor(JaegerExporter())
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

logger = get_task_logger(__name__)

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "sc4")
MONGO_DB_SCHEDULES = os.getenv("MONGO_DB_SCHEDULES", "schedules")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL")

config = {
    "mongodb_scheduler_url": MONGO_URI,
    "mongodb_scheduler_db": MONGO_DB,
    "mongodb_scheduler_collection": MONGO_DB_SCHEDULES,
    "broker": CELERY_BROKER_URL,
}


@signals.worker_process_init.connect(weak=False)
def init_celery_tracing(*args, **kwargs):
    CeleryInstrumentor().instrument()
    LoggingInstrumentor().instrument()


@signals.beat_init.connect(weak=False)
def init_celery_beat_tracing(*args, **kwargs):
    CeleryInstrumentor().instrument()
    LoggingInstrumentor().instrument()

    mongo_client = pymongo.MongoClient(MONGO_URI)
    db = mongo_client[MONGO_DB]
    collist = db.list_collection_names()
    if not "targets" in collist:
        mycol = db["targets"]


# //using rabbitmq as the message broker
app = Celery("sc4snmp")
app.conf.update(**config)

# app.conf.beat_schedule = {
#   'call-every-30-seconds': {
#     'task': 'splunk-connect-collector.tasks.hello',
#     'schedule': 30.0 #time-interval type
#    }
# }


app.autodiscover_tasks(
    packages=[
        "splunk_connect_for_snmp",
        "splunk_connect_for_snmp.enrich",
        "splunk_connect_for_snmp.inventory",
        "splunk_connect_for_snmp.snmp",
        "splunk_connect_for_snmp.splunk",
    ]
)

from splunk_connect_for_snmp import customtaskmanager

schedule_data_create_interval = {
    "name": "sc4snmp;inventory;seed",
    "task": "splunk_connect_for_snmp.inventory.tasks.inventory_seed",
    "args": [],
    "kwargs": {
        "url": "https://gist.githubusercontent.com/rfaircloth-splunk/0590fa671f794902005257bcbd2ee274/raw/90f6930aaace6ca5aba8edc8c57f38552049c1d1/snmp_inventory.csv"
    },
    "interval": {"every": 20, "period": "seconds"},
    "enabled": True,
    "run_immediately": True,
}

periodic_obj = customtaskmanager.CustomPeriodicTaskManage()
print(periodic_obj.manage_task(**schedule_data_create_interval))
