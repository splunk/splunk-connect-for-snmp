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

try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass

import asyncio
import os

import yaml
from celery import Celery, chain, signals
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
from pysnmp.proto import rfc1902

from splunk_connect_for_snmp.snmp.const import AuthProtocolMap, PrivProtocolMap
from splunk_connect_for_snmp.snmp.tasks import trap
from splunk_connect_for_snmp.splunk.tasks import prepare, send

provider = TracerProvider()
processor = BatchSpanProcessor(JaegerExporter())
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

logger = get_task_logger(__name__)

CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.yaml")


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


def getSecretValue(
    location: str, key: str, default: str = None, required: bool = False
) -> str:
    source = os.path.join(location, key)
    result = default
    if os.path.exists(source):
        with open(os.path.join(location, key)) as file:
            result = file.read().replace("\n", "")
    elif required:
        raise Exception(f"Required secret key {key} not found in {location}")
    return result


# Callback function for receiving notifications
# noinspection PyUnusedLocal
def cbFun(snmpEngine, stateReference, contextEngineId, contextName, varBinds, cbCtx):
    transportDomain, transportAddress = snmpEngine.msgAndPduDsp.getTransportInfo(
        stateReference
    )
    data = []
    device_ip = snmpEngine.msgAndPduDsp.getTransportInfo(stateReference)[1][0]

    for name, val in varBinds:
        data.append((name.prettyPrint(), val.prettyPrint()))

    work = {"data": data, "host": device_ip}

    my_chain = chain(trap.s(work), prepare.s(), send.s())
    result = my_chain.apply_async()


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

    # Transport setup

    # UDP over IPv4, first listening interface/port
    config.addTransport(
        snmpEngine,
        udp.domainName + (1,),
        udp.UdpTransport().openServerMode(("0.0.0.0", 2162)),
    )
    with open(CONFIG_PATH) as file:
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
            userName = getSecretValue(location, "userName", required=True)

            authKey = getSecretValue(location, "authKey", required=False)
            privKey = getSecretValue(location, "privKey", required=False)

            authProtocol = getSecretValue(location, "authProtocol", required=False)
            authProtocol = AuthProtocolMap.get(authProtocol.upper(), "NONE")

            privProtocol = getSecretValue(
                location, "privProtocol", required=False, default="NONE"
            )
            privProtocol = PrivProtocolMap.get(privProtocol.upper(), "NONE")

            securityEngineId = getSecretValue(
                location, "securityEngineId", required=False, default=None
            )
            if securityEngineId:
                securityEngineId = rfc1902.OctetString(
                    hexValue=str(securityEngineId)
                )

            securityName = getSecretValue(location, "securityName", required=False)

            authKeyType = int(
                getSecretValue(location, "authKeyType", required=False, default="0")
            )

            privKeyType = int(
                getSecretValue(location, "privKeyType", required=False, default="0")
            )
            config.addV3User(
                snmpEngine,
                userName=userName,
                authProtocol=authProtocol,
                authKey=authKey,
                privProtocol=privProtocol,
                privKey=privKey,
                securityEngineId=securityEngineId,
                securityName=None,
                authKeyType=0,
                privKeyType=0,
                contextEngineId=None,
            )

    # Register SNMP Application at the SNMP engine
    ntfrcv.NotificationReceiver(snmpEngine, cbFun)

    # Run asyncio main loop
    loop.run_forever()
