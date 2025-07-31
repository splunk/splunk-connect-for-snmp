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
from contextlib import suppress

from celery.utils.log import get_task_logger
from pysnmp.proto.api import v2c

from splunk_connect_for_snmp.common.hummanbool import human_bool
from splunk_connect_for_snmp.snmp.auth import get_secret_value

with suppress(ImportError, OSError):
    from dotenv import load_dotenv

    load_dotenv()

import asyncio
import os
import sys
from typing import Any, Dict

import yaml
from celery import Celery, chain
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from pysnmp.carrier.asyncio.dgram import udp, udp6
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
IPv6_ENABLED = human_bool(os.getenv("IPv6_ENABLED", "false").lower())
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
PYSNMP_DEBUG = os.getenv("PYSNMP_DEBUG", "")

logging.basicConfig(
    format='[%(asctime)s: %(levelname)s/%(name)s] %(message)s',
    level=getattr(logging, LOG_LEVEL),
    stream=sys.stdout,
    force=True  # This will override any existing configuration
)

# Now create the module logger
logger = logging.getLogger(__name__)

# Configure third-party loggers
logging.getLogger('pymongo').setLevel(logging.WARNING)
logging.getLogger('mongodb').setLevel(logging.WARNING)

# Remove the direct logging call and use logger instead
logger.info(f"Logging level set to {LOG_LEVEL}")

if PYSNMP_DEBUG:
    # Usage: PYSNMP_DEBUG=dsp,msgproc,io

    # List of available debug flags:
    # io, dsp, msgproc, secmod, mibbuild, mibview, mibinstrum, acl, proxy, app, all

    from pysnmp import debug

    debug_flags = list(debug.flagMap.keys())
    enabled_debug_flags = [
        debug_flag.strip()
        for debug_flag in PYSNMP_DEBUG.split(",")
        if debug_flag.strip() in debug_flags
    ]

    if enabled_debug_flags:
        debug.setLogger(
            debug.Debug(*enabled_debug_flags, options={"loggerName": logger})
        )


# //using rabbitmq as the message broker
app = Celery("sc4snmp_traps")
app.config_from_object("splunk_connect_for_snmp.celery_config")

trap_task_signature = trap.s
prepare_task_signature = prepare.s
send_task_signature = send.s


# Callback function for receiving notifications
# noinspection PyUnusedLocal
def cb_fun(
    snmp_engine, state_reference, context_engine_id, context_name, varbinds, cb_ctx
):
    logger.debug(
        'Notification from ContextEngineId "%s", ContextName "%s"'
        % (context_engine_id.prettyPrint(), context_name.prettyPrint())
    )

    exec_context = snmp_engine.observer.getExecutionContext(
        "rfc3412.receiveMessage:request"
    )

    data = []
    device_ip = exec_context["transportAddress"][0]

    for name, val in varbinds:
        data.append((name.prettyPrint(), val.prettyPrint()))

    work = {"data": data, "host": device_ip}
    my_chain = chain(
        trap_task_signature(work).set(queue="traps").set(priority=5),
        prepare_task_signature().set(queue="send").set(priority=1),
        send_task_signature().set(queue="send").set(priority=0),
    )
    _ = my_chain.apply_async()


# Callback function for logging traps authentication errors
def authentication_observer_cb_fun(snmp_engine, execpoint, variables, contexts):
    logger.error(
        f"Security Model failure for device {variables.get('transportAddress', None)}: "
        f"{variables.get('statusInformation', {}).get('errorIndication', None)}"
    )


app.autodiscover_tasks(
    packages=[
        "splunk_connect_for_snmp",
        "splunk_connect_for_snmp.enrich",
        "splunk_connect_for_snmp.inventory",
        "splunk_connect_for_snmp.splunk",
        "splunk_connect_for_snmp.snmp",
    ]
)


def add_communities(config_base, snmp_engine):
    idx = 0
    if "communities" in config_base:
        if "2c" in config_base["communities"]:
            for community in config_base["communities"]["2c"]:
                idx += 1
                config.addV1System(snmp_engine, idx, community)
        if "1" in config_base["communities"] or 1 in config_base["communities"]:
            v = config_base["communities"].get("1", config_base["communities"].get(1))
            for community in v:
                idx += 1
                config.addV1System(snmp_engine, idx, community)


def main():
    logger.info("Logging configured")
    logger.debug("Logging DEBUG configured")
    # Get the event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Create SNMP engine with autogenernated engineID and pre-bound
    # to socket transport dispatcher
    snmp_engine = engine.SnmpEngine()

    # Register a callback function to log errors with traps authentication
    observer_context: Dict[Any, Any] = {}
    snmp_engine.observer.registerObserver(
        authentication_observer_cb_fun,
        "rfc2576.prepareDataElements:sm-failure",
        "rfc3412.prepareDataElements:sm-failure",
        cbCtx=observer_context,
    )

    # UDP socket over IPv6 listens also for IPv4
    if IPv6_ENABLED:
        config.addTransport(
            snmp_engine,
            udp6.domainName,
            udp6.Udp6Transport().openServerMode(("::", 2162)),
        )
    else:
        # UDP over IPv4, first listening interface/port
        config.addTransport(
            snmp_engine,
            udp.domainName,
            udp.UdpTransport().openServerMode(("0.0.0.0", 2162)),
        )

    with open(CONFIG_PATH, encoding="utf-8") as file:
        config_base = yaml.safe_load(file)

    add_communities(config_base, snmp_engine)

    if "usernameSecrets" in config_base:
        for secret in config_base["usernameSecrets"]:
            location = os.path.join("secrets/snmpv3", secret)
            username = get_secret_value(
                location, "userName", required=True, default=None
            )

            auth_key = get_secret_value(location, "authKey", required=False)
            priv_key = get_secret_value(location, "privKey", required=False)

            auth_protocol = get_secret_value(location, "authProtocol", required=False)
            logger.debug(f"authProtocol: {auth_protocol}")
            auth_protocol = AuthProtocolMap.get(auth_protocol.upper(), "NONE")

            priv_protocol = get_secret_value(
                location, "privProtocol", required=False, default="NONE"
            )
            logger.debug(f"privProtocol: {priv_protocol}")
            priv_protocol = PrivProtocolMap.get(priv_protocol.upper(), "NONE")

            for security_engine_id in SECURITY_ENGINE_ID_LIST:
                config.addV3User(
                    snmp_engine,
                    userName=username,
                    authProtocol=auth_protocol,
                    authKey=auth_key,
                    privProtocol=priv_protocol,
                    privKey=priv_key,
                    securityEngineId=v2c.OctetString(hexValue=security_engine_id),
                )
                logger.debug(
                    f"V3 users: {username} auth {auth_protocol} authkey {len(auth_key)*'*'} privprotocol {priv_protocol} "
                    f"privkey {len(priv_key)*'*'} securityEngineId {len(security_engine_id)*'*'}"
                )

    # Register SNMP Application at the SNMP engine
    ntfrcv.NotificationReceiver(snmp_engine, cb_fun)

    # Run asyncio main loop
    loop.run_forever()
