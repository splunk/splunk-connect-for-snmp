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

from pysnmp.proto.api import v2c

from splunk_connect_for_snmp.common.customised_json_formatter import (
    CustomisedJSONFormatter,
)
from splunk_connect_for_snmp.snmp.auth import get_secret_value

try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass

import asyncio
import os

import yaml
from celery import Celery, chain, signals
from opentelemetry import trace

# from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.trace import TracerProvider

# from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity import config, engine
from pysnmp.entity.rfc3413 import ntfrcv

from splunk_connect_for_snmp.snmp.const import AuthProtocolMap, PrivProtocolMap
from splunk_connect_for_snmp.snmp.tasks import trap
from splunk_connect_for_snmp.splunk.tasks import prepare, send

provider = TracerProvider()
trace.set_tracer_provider(provider)

CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.yaml")
SECURITY_ENGINE_ID_LIST = os.getenv("SNMP_V3_SECURITY_ENGINE_ID", "80003a8c04").split(
    ","
)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL), format="%(asctime)s %(levelname)s %(message)s"
)

formatter = CustomisedJSONFormatter()
# //using rabbitmq as the message broker
app = Celery("sc4snmp_traps")
app.config_from_object("splunk_connect_for_snmp.celery_config")

trap_task_signature = trap.s
prepare_task_signature = prepare.s
send_task_signature = send.s


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


# Callback function for receiving notifications
# noinspection PyUnusedLocal
def cbFun(snmpEngine, stateReference, contextEngineId, contextName, varBinds, cbCtx):
    transportDomain, transportAddress = snmpEngine.msgAndPduDsp.getTransportInfo(
        stateReference
    )
    logging.debug(
        'Notification from ContextEngineId "%s", ContextName "%s"'
        % (contextEngineId.prettyPrint(), contextName.prettyPrint())
    )

    execContext = snmpEngine.observer.getExecutionContext(
        "rfc3412.receiveMessage:request"
    )

    data = []
    device_ip = execContext["transportAddress"][0]

    for name, val in varBinds:
        data.append((name.prettyPrint(), val.prettyPrint()))

    work = {"data": data, "host": device_ip}
    my_chain = chain(
        trap_task_signature(work).set(queue="traps").set(priority=5),
        prepare_task_signature().set(queue="send").set(priority=1),
        send_task_signature().set(queue="send").set(priority=0),
    )
    _ = my_chain.apply_async()


app.autodiscover_tasks(
    packages=[
        "splunk_connect_for_snmp",
        "splunk_connect_for_snmp.enrich",
        "splunk_connect_for_snmp.inventory",
        "splunk_connect_for_snmp.splunk",
        "splunk_connect_for_snmp.snmp",
    ]
)


def main():
    # Get the event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # Create SNMP engine with autogenernated engineID and pre-bound
    # to socket transport dispatcher
    snmpEngine = engine.SnmpEngine()
    # UDP over IPv4, first listening interface/port
    config.addTransport(
        snmpEngine,
        udp.domainName,
        udp.UdpTransport().openServerMode(("0.0.0.0", 2162)),
    )
    with open(CONFIG_PATH, encoding="utf-8") as file:
        config_base = yaml.safe_load(file)
    idx = 0
    if "communities" in config_base:
        if "2c" in config_base["communities"]:
            for community in config_base["communities"]["2c"]:
                idx += 1
                config.addV1System(snmpEngine, idx, community)

    if "usernameSecrets" in config_base:
        for secret in config_base["usernameSecrets"]:
            location = os.path.join("secrets/snmpv3", secret)
            userName = get_secret_value(
                location, "userName", required=True, default=None
            )

            authKey = get_secret_value(location, "authKey", required=False)
            privKey = get_secret_value(location, "privKey", required=False)

            authProtocol = get_secret_value(location, "authProtocol", required=False)
            logging.debug(f"authProtocol: {authProtocol}")
            authProtocol = AuthProtocolMap.get(authProtocol.upper(), "NONE")

            privProtocol = get_secret_value(
                location, "privProtocol", required=False, default="NONE"
            )
            logging.debug(f"privProtocol: {privProtocol}")
            privProtocol = PrivProtocolMap.get(privProtocol.upper(), "NONE")

            for security_engine_id in SECURITY_ENGINE_ID_LIST:
                config.addV3User(
                    snmpEngine,
                    userName=userName,
                    authProtocol=authProtocol,
                    authKey=authKey,
                    privProtocol=privProtocol,
                    privKey=privKey,
                    securityEngineId=v2c.OctetString(hexValue=security_engine_id),
                )
                logging.debug(
                    f"V3 users: {userName} auth {authProtocol} authkey {authKey} privprotocol {privProtocol} "
                    f"privkey {privKey} securityEngineId {security_engine_id}"
                )

    # Register SNMP Application at the SNMP engine
    ntfrcv.NotificationReceiver(snmpEngine, cbFun)

    # Run asyncio main loop
    loop.run_forever()
