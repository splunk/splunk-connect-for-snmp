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

from pyasn1.codec.ber import decoder
from pyasn1.error import PyAsn1Error
from pyasn1.type import univ
from pysnmp.proto.api import v2c

from splunk_connect_for_snmp.common.common import (
    disable_mongo_logging,
    human_bool,
    wait_for_mongodb_replicaset,
)
from splunk_connect_for_snmp.snmp.auth import get_secret_value
from splunk_connect_for_snmp.snmp.manager import format_trap_varbind_value
from splunk_connect_for_snmp.snmp.trap_varbind_limit import (
    limit_trap_varbind_pairs,
    log_trap_varbind_limit_config,
)

with suppress(ImportError, OSError):
    from dotenv import load_dotenv

    load_dotenv()

import asyncio
import os
import sys
from typing import Any, Dict, Tuple

import pymongo
import yaml
from celery import Celery, chain
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from pysnmp.carrier.asyncio.dgram import udp, udp6
from pysnmp.entity import config, engine
from pysnmp.entity.rfc3413 import ntfrcv

from splunk_connect_for_snmp.common.collection_manager import EngineIdManager
from splunk_connect_for_snmp.snmp.const import AuthProtocolMap, PrivProtocolMap
from splunk_connect_for_snmp.snmp.tasks import trap
from splunk_connect_for_snmp.splunk.tasks import prepare, send

provider = TracerProvider()
trace.set_tracer_provider(provider)

CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.yaml")
MONGO_URI = os.getenv("MONGO_URI")
SECURITY_ENGINE_ID_LIST = os.getenv("SNMP_V3_SECURITY_ENGINE_ID", "80003a8c04").split(
    ","
)
INCLUDE_SECURITY_CONTEXT_ID = human_bool(
    os.getenv("INCLUDE_SECURITY_CONTEXT_ID", "false")
)
DISCOVER_ENGINE_ID = human_bool(os.getenv("DISCOVER_ENGINE_ID", "false"))
IPv6_ENABLED = human_bool(os.getenv("IPv6_ENABLED", "false").lower())
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
PYSNMP_DEBUG = os.getenv("PYSNMP_DEBUG", "")
DISABLE_MONGO_DEBUG_LOGGING = human_bool(
    os.getenv("DISABLE_MONGO_DEBUG_LOGGING", "true")
)

# Now create the module logger
logging.basicConfig(
    format="[%(asctime)s: %(levelname)s/%(name)s] %(message)s",
    level=getattr(logging, LOG_LEVEL),
    stream=sys.stdout,
    force=True,  # This will override any existing configuration
)

logger = logging.getLogger(__name__)
log_trap_varbind_limit_config(logger)
wait_for_mongodb_replicaset(logger)

if DISABLE_MONGO_DEBUG_LOGGING:
    disable_mongo_logging()

if PYSNMP_DEBUG:
    # Usage: PYSNMP_DEBUG=dsp,msgproc,io

    # List of available debug flags:
    # io, dsp, msgproc, secmod, mibbuild, mibview, mibinstrum, acl, proxy, app, all

    from pysnmp import debug

    debug_flags = list(debug.FLAG_MAP.keys())
    enabled_debug_flags = [
        debug_flag.strip()
        for debug_flag in PYSNMP_DEBUG.split(",")
        if debug_flag.strip() in debug_flags
    ]

    if enabled_debug_flags:
        debug.set_logger(
            debug.Debug(*enabled_debug_flags, options={"loggerName": logger})
        )

engine_id_manager = None

wait_for_mongodb_replicaset(logger)
app = Celery("sc4snmp_traps")
app.config_from_object("splunk_connect_for_snmp.celery_config")

trap_task_signature = trap.s
prepare_task_signature = prepare.s
send_task_signature = send.s


def decode_security_context(
    hexstr: bytes,
) -> Tuple[str | None, str | None]:
    """
    Decodes SNMPv3 security context from ASN.1 bytes.
    Returns (engineID hex string, USM userName) on success, or (None, None) on failure.
    Sometimes (for example in ERICSSON devices) the engineID is the only place where device IP is stored.
    """
    try:
        decoded_message, _ = decoder.decode(hexstr, asn1Spec=univ.Sequence())
        msg_version = decoded_message.getComponentByPosition(0)
        if msg_version._value != 3:
            logger.warning(
                "SNMP message version is not 3, skipping security context decoding."
            )
            return None, None
        msg_security_parameters_raw = decoded_message.getComponentByPosition(
            2
        ).asOctets()
        usm_message, _ = decoder.decode(
            msg_security_parameters_raw, asn1Spec=univ.Sequence()
        )
        usm_engine_id_obj = usm_message.getComponentByPosition(0)
        usm_engine_id_bytes = usm_engine_id_obj.asOctets()
        usm_username = usm_message.getComponentByPosition(3).asOctets().decode("utf-8")
        return usm_engine_id_bytes.hex(), usm_username
    except PyAsn1Error as e:
        logger.error(f"ASN.1 decoding error: {e}")
    except Exception as e:
        logger.error(f"Error decoding SNMPv3 engineID: {e}")
    return None, None


def _sync_engine_ids_with_mongo():
    """
    Bidirectional sync between SECURITY_ENGINE_ID_LIST taken from configuration file and MongoDB engine_id_records collection.
    Returns the merged set of all known engine IDs.
    """
    env_ids = {eid.strip() for eid in SECURITY_ENGINE_ID_LIST if (eid or "").strip()}

    for eid in env_ids:
        engine_id_manager.save_engine_id("config", eid)

    mongo_engine_ids = engine_id_manager.get_unique_engine_ids()
    merged = env_ids | mongo_engine_ids

    logger.info(
        "Engine ID sync: %d from env var, %d from MongoDB, %d total unique",
        len(env_ids),
        len(mongo_engine_ids),
        len(merged),
    )
    return merged


# Cache of engineID read from raw datagram (before pysnmp parsing).
# Key: normalized (host, port); value: engineID hex string.
_engine_id_from_raw_message: Dict[Tuple[Any, ...], str] = {}

# Dynamic V3 user registration: when a new engineID is seen in a trap, add it for all configured users
# so pysnmp can authenticate the same message. Set in main() after loading config.
_snmp_engine_for_discovery: Any = None
_v3_user_configs_for_discovery: list[Dict[str, Any]] = []
_added_engine_ids: set[str] = set()


def _normalize_transport_address(transport_address: Any) -> Tuple[Any, ...]:
    """Normalize transport address to a hashable tuple for use as cache key."""
    if isinstance(transport_address, (list, tuple)) and len(transport_address) >= 2:
        host, port = transport_address[0], transport_address[1]
        if isinstance(host, str) and "%" in host:
            host = host.split("%")[0]
        return (host, port)
    return (transport_address,)


def get_engine_id_from_raw_message(transport_address: Any) -> str | None:
    """Return engineID previously extracted from raw datagram for this address, if any."""
    key = _normalize_transport_address(transport_address)
    return _engine_id_from_raw_message.get(key)


def _add_v3_user_for_new_engine_id(engine_id: str) -> bool:
    """
    If engine_id is new, add it as securityEngineId for all configured V3 users so the
    incoming trap can be authenticated. Returns True if the engine_id was newly added.
    """
    engine_id = (engine_id or "").strip().lower()
    if not engine_id or engine_id in _added_engine_ids:
        return False
    if _snmp_engine_for_discovery is None or not _v3_user_configs_for_discovery:
        return False
    for uc in _v3_user_configs_for_discovery:
        config.add_v3_user(
            _snmp_engine_for_discovery,
            userName=uc["userName"],
            authProtocol=uc["authProtocol"],
            authKey=uc["authKey"],
            privProtocol=uc["privProtocol"],
            privKey=uc["privKey"],
            securityEngineId=v2c.OctetString(hexValue=engine_id),
        )
    _added_engine_ids.add(engine_id)
    logger.info(
        "Added securityEngineId %s for all V3 users so trap can be processed",
        engine_id,
    )
    return True


class _EngineIDCaptureUdpTransport(udp.UdpAsyncioTransport):
    """UDP transport that extracts SNMPv3 engineID from raw datagram and adds it as V3 user before pysnmp parses."""

    def datagram_received(self, datagram: bytes, transport_address: Any) -> None:
        if DISCOVER_ENGINE_ID:
            engine_id, username = decode_security_context(datagram)
            if engine_id:
                key = _normalize_transport_address(transport_address)
                _engine_id_from_raw_message[key] = engine_id
                if username and any(
                    uc["userName"] == username for uc in _v3_user_configs_for_discovery
                ):
                    _add_v3_user_for_new_engine_id(engine_id)
        super().datagram_received(datagram, transport_address)


class _EngineIDCaptureUdp6Transport(udp6.Udp6AsyncioTransport):
    """UDP6 transport that extracts SNMPv3 engineID from raw datagram and adds it as V3 user before pysnmp parses."""

    def datagram_received(self, datagram: bytes, transport_address: Any) -> None:
        if DISCOVER_ENGINE_ID:
            engine_id, username = decode_security_context(datagram)
            if engine_id:
                key = _normalize_transport_address(transport_address)
                _engine_id_from_raw_message[key] = engine_id
                if username and any(
                    uc["userName"] == username for uc in _v3_user_configs_for_discovery
                ):
                    _add_v3_user_for_new_engine_id(engine_id)
        super().datagram_received(datagram, transport_address)


# Callback function for receiving notifications
# noinspection PyUnusedLocal
def cb_fun(
    snmp_engine: engine.SnmpEngine,
    state_reference,
    context_engine_id,
    context_name,
    varbinds,
    cb_ctx,
):
    logger.debug(
        'Notification from ContextEngineId "%s", ContextName "%s"'
        % (context_engine_id.prettyPrint(), context_name.prettyPrint())
    )
    exec_context = snmp_engine.observer.get_execution_context(
        "rfc3412.receiveMessage:request"
    )

    data = []
    device_ip = exec_context["transportAddress"][0]

    logger.debug("Device IP is %s", device_ip)

    for name, val in limit_trap_varbind_pairs(varbinds, log=logger, source=device_ip):
        data.append((name.prettyPrint(), format_trap_varbind_value(val)))

    work = {"data": data, "host": device_ip}
    decoded_engine_id, _ = decode_security_context(exec_context.get("wholeMsg"))
    if decoded_engine_id:
        if engine_id_manager is not None:
            engine_id_manager.save_engine_id(device_ip, decoded_engine_id)
        if INCLUDE_SECURITY_CONTEXT_ID:
            work["fields"] = {"context_engine_id": decoded_engine_id}
    my_chain = chain(
        trap_task_signature(work).set(queue="traps").set(priority=5),
        prepare_task_signature().set(queue="send").set(priority=1),
        send_task_signature().set(queue="send").set(priority=0),
    )
    _ = my_chain.apply_async()


# Callback function for logging traps authentication errors
def authentication_observer_cb_fun(snmp_engine, execpoint, variables, contexts):
    transport_address = variables.get("transportAddress", None)
    engine_id = (
        get_engine_id_from_raw_message(transport_address) if transport_address else None
    )
    msg = (
        f"Security Model failure for device {transport_address}: "
        f"{variables.get('statusInformation', {}).get('errorIndication', None)}"
    )
    if engine_id:
        msg += f" (security_engine_id from incoming message: {engine_id})"
    logger.error(msg)


app.autodiscover_tasks(
    packages=[
        "splunk_connect_for_snmp",
        "splunk_connect_for_snmp.enrich",
        "splunk_connect_for_snmp.inventory",
        "splunk_connect_for_snmp.splunk",
        "splunk_connect_for_snmp.snmp",
    ]
)


def add_communities(config_base: dict, snmp_engine: engine.SnmpEngine):
    idx = 0
    if "communities" in config_base:
        if "2c" in config_base["communities"]:
            for community in config_base["communities"]["2c"]:
                idx += 1
                config.add_v1_system(snmp_engine, str(idx), community)
        if "1" in config_base["communities"] or 1 in config_base["communities"]:
            v = config_base["communities"].get("1", config_base["communities"].get(1))
            for community in v:
                idx += 1
                config.add_v1_system(snmp_engine, str(idx), community)


def main():
    global engine_id_manager

    # Get the event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    if MONGO_URI:
        mongo_client = pymongo.MongoClient(MONGO_URI)
        engine_id_manager = EngineIdManager(mongo_client)
        all_engine_ids = _sync_engine_ids_with_mongo()
    else:
        logger.warning("MONGO_URI is not set; engine ID records will not be persisted.")
        all_engine_ids = {
            eid.strip() for eid in SECURITY_ENGINE_ID_LIST if (eid or "").strip()
        }

    # Create SNMP engine with autogenernated engineID and pre-bound
    # to socket transport dispatcher
    snmp_engine = engine.SnmpEngine()

    # Register a callback function to log errors with traps authentication
    observer_context: Dict[Any, Any] = {}
    snmp_engine.observer.register_observer(
        authentication_observer_cb_fun,
        "rfc2576.prepareDataElements:sm-failure",
        "rfc3412.prepareDataElements:sm-failure",
        cbCtx=observer_context,
    )

    # UDP socket over IPv6 listens also for IPv4 (with engineID capture from raw datagram before parse)
    if IPv6_ENABLED:
        config.add_transport(
            snmp_engine,
            udp6.DOMAIN_NAME,
            _EngineIDCaptureUdp6Transport().open_server_mode(("::", 2162)),
        )
    else:
        # UDP over IPv4, first listening interface/port (with engineID capture from raw datagram before parse)
        config.add_transport(
            snmp_engine,
            udp.DOMAIN_NAME,
            _EngineIDCaptureUdpTransport().open_server_mode(("0.0.0.0", 2162)),
        )

    with open(CONFIG_PATH, encoding="utf-8") as file:
        config_base = yaml.safe_load(file)

    add_communities(config_base, snmp_engine)

    if "usernameSecrets" in config_base:
        _added_engine_ids.update(eid.lower() for eid in all_engine_ids)
        v3_user_configs: list[Dict[str, Any]] = []

        for secret in config_base["usernameSecrets"]:
            location = os.path.join("secrets/snmpv3", secret)
            username = get_secret_value(
                location, "userName", required=True, default=None
            )

            auth_key = get_secret_value(
                location, "authKey", required=False, default=None
            )
            priv_key = get_secret_value(
                location, "privKey", required=False, default=None
            )

            auth_protocol = get_secret_value(location, "authProtocol", required=False)
            logger.debug(f"authProtocol: {auth_protocol}")
            auth_protocol = AuthProtocolMap.get(auth_protocol.upper(), "NONE")

            priv_protocol = get_secret_value(
                location, "privProtocol", required=False, default="NONE"
            )
            logger.debug(f"privProtocol: {priv_protocol}")
            priv_protocol = PrivProtocolMap.get(priv_protocol.upper(), "NONE")

            v3_user_configs.append(
                {
                    "userName": username,
                    "authProtocol": auth_protocol,
                    "authKey": auth_key,
                    "privProtocol": priv_protocol,
                    "privKey": priv_key,
                }
            )

            for security_engine_id in all_engine_ids:
                config.add_v3_user(
                    snmp_engine,
                    userName=username,
                    authProtocol=auth_protocol,
                    authKey=auth_key if auth_key else None,
                    privProtocol=priv_protocol,
                    privKey=priv_key if priv_key else None,
                    securityEngineId=v2c.OctetString(hexValue=security_engine_id),
                )
                logger.debug(
                    f"V3 users: {username} auth {auth_protocol} authkey {len(str(auth_key))*'*'} privprotocol {priv_protocol} "
                    f"privkey {len(str(priv_key))*'*'} securityEngineId {len(security_engine_id)*'*'}"
                )

        # Allow transport to add newly seen engineIDs as V3 users so traps are processed successfully
        global _snmp_engine_for_discovery, _v3_user_configs_for_discovery
        _snmp_engine_for_discovery = snmp_engine
        _v3_user_configs_for_discovery = v3_user_configs

    # Register SNMP Application at the SNMP engine
    ntfrcv.NotificationReceiver(snmp_engine, cb_fun)

    # Run asyncio main loop
    loop.run_forever()
