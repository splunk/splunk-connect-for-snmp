import asyncio

from celery import Celery, signals, chain
from celery.utils.log import get_task_logger
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity import config, engine
from pysnmp.entity.rfc3413 import ntfrcv

from splunk_connect_for_snmp.snmp.tasks import trap
from splunk_connect_for_snmp.splunk.tasks import prepare, send

provider = TracerProvider()
processor = BatchSpanProcessor(JaegerExporter())
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

logger = get_task_logger(__name__)

# //using rabbitmq as the message broker
app = Celery("sc4snmp_traps")
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
        "splunk_connect_for_snmp.splunk",
        "splunk_connect_for_snmp.snmp",
    ]
)

# Get the event loop for this thread
loop = asyncio.get_event_loop()

# Create SNMP engine with autogenernated engineID and pre-bound
# to socket transport dispatcher
snmpEngine = engine.SnmpEngine()

# Transport setup

# UDP over IPv4, first listening interface/port
config.addTransport(
    snmpEngine,
    udp.domainName + (1,),
    udp.UdpTransport().openServerMode(("127.0.0.1", 2062)),
)

# SecurityName <-> CommunityName mapping
config.addV1System(snmpEngine, "my-area", "public")

# Callback function for receiving notifications
# noinspection PyUnusedLocal
def cbFun(snmpEngine, stateReference, contextEngineId, contextName, varBinds, cbCtx):
    transportDomain, transportAddress = snmpEngine.msgAndPduDsp.getTransportInfo(
        stateReference
    )
    print(
        "Notification from %s, SNMP Engine %s, Context %s"
        % (transportAddress, contextEngineId.prettyPrint(), contextName.prettyPrint())
    )
    data = []
    for name, val in varBinds:
        data.append((name.prettyPrint(), val.prettyPrint()))
        print(f"{name.prettyPrint()} = {val.prettyPrint()}")

    work = {"data": data, "host": transportAddress[0]}

    my_chain = chain(trap.s(work), prepare.s(), send.s())
    result = my_chain.apply_async()


# Register SNMP Application at the SNMP engine
ntfrcv.NotificationReceiver(snmpEngine, cbFun)

# Run asyncio main loop
loop.run_forever()
