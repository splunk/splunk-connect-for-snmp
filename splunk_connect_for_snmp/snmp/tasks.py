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
import re
from contextlib import suppress

from pysnmp.smi.error import NoSuchObjectError, SmiError

from splunk_connect_for_snmp.snmp.exceptions import SnmpActionError

with suppress(ImportError, OSError):
    from dotenv import load_dotenv

    load_dotenv()

import os
import socket
import time

import pymongo
from celery import shared_task
from celery.utils.log import get_task_logger
from mongolock import MongoLock, MongoLockLocked
from pysnmp.smi.rfc1902 import ObjectIdentity, ObjectType

from splunk_connect_for_snmp.common.common import human_bool
from splunk_connect_for_snmp.common.custom_cache import ttl_lru_cache
from splunk_connect_for_snmp.snmp.manager import Poller, get_inventory, value_as_best

logger = get_task_logger(__name__)

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "sc4snmp")
CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.yaml")
WALK_RETRY_MAX_INTERVAL = int(os.getenv("WALK_RETRY_MAX_INTERVAL", "180"))
WALK_MAX_RETRIES = int(os.getenv("WALK_MAX_RETRIES", "5"))
SPLUNK_SOURCETYPE_TRAPS = os.getenv("SPLUNK_SOURCETYPE_TRAPS", "sc4snmp:traps")
OID_VALIDATOR = re.compile(r"^([0-2])((\.0)|(\.[1-9]\d*))*$")
UNRESOLVED_TRAP_GROUP_KEY = "sc4snmp::unresolved"
UNRESOLVED_FIELD_PREFIX = "unresolved::"
RESOLVE_TRAP_ADDRESS = os.getenv("RESOLVE_TRAP_ADDRESS", "false")
MAX_DNS_CACHE_SIZE_TRAPS = int(os.getenv("MAX_DNS_CACHE_SIZE_TRAPS", "100"))
TTL_DNS_CACHE_TRAPS = int(os.getenv("TTL_DNS_CACHE_TRAPS", "1800"))
IPv6_ENABLED = human_bool(os.getenv("IPv6_ENABLED", "false").lower())


@shared_task(
    bind=True,
    base=Poller,
    retry_backoff=30,
    retry_backoff_max=WALK_RETRY_MAX_INTERVAL,
    max_retries=WALK_MAX_RETRIES,
    autoretry_for=(
        MongoLockLocked,
        SnmpActionError,
    ),
    throws=(
        SnmpActionError,
        SnmpActionError,
    ),
)
def walk(self, **kwargs):
    address = kwargs["address"]
    profile = kwargs.get("profile", [])
    group = kwargs.get("group")
    chain_of_tasks_expiry_time = kwargs.get("chain_of_tasks_expiry_time")
    if profile:
        profile = [profile]
    mongo_client = pymongo.MongoClient(MONGO_URI)
    mongo_db = mongo_client[MONGO_DB]
    mongo_inventory = mongo_db.inventory

    ir = get_inventory(mongo_inventory, address)
    retry = True
    while retry:
        retry, result = self.do_work(ir, walk=True, profiles=profile)

    # After a Walk tell schedule to recalc
    work = {
        "time": time.time(),
        "address": address,
        "result": result,
        "chain_of_tasks_expiry_time": chain_of_tasks_expiry_time,
    }
    if group:
        work["group"] = group

    return work


@shared_task(
    bind=True,
    base=Poller,
    default_retry_delay=5,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=1,
    retry_jitter=True,
    expires=30,
)
def poll(self, **kwargs):

    address = kwargs["address"]
    profiles = kwargs["profiles"]
    group = kwargs.get("group")
    mongo_client = pymongo.MongoClient(MONGO_URI)
    mongo_db = mongo_client[MONGO_DB]
    mongo_inventory = mongo_db.inventory

    ir = get_inventory(mongo_inventory, address)
    _, result = self.do_work(ir, profiles=profiles)

    # After a Walk tell schedule to recalc
    work = {
        "time": time.time(),
        "address": address,
        "result": result,
        "detectchange": False,
        "frequency": kwargs["frequency"],
    }
    if group:
        work["group"] = group

    return work


@ttl_lru_cache(maxsize=MAX_DNS_CACHE_SIZE_TRAPS, ttl=TTL_DNS_CACHE_TRAPS)
def resolve_address(address: str):
    try:
        dns_result = socket.gethostbyaddr(address)
        result = dns_result[0]
    except socket.herror:
        logger.info(f"Traps: address {address} can't be resolved.")
        result = address
    return result


def _oids_for_mib_lookup(varbind):
    """Return numeric OID strings from a trap varbind name and/or value."""
    name, value = varbind
    for candidate in (name, value):
        if OID_VALIDATOR.match(candidate):
            yield candidate


def _is_enterprise_oid(oid: str) -> bool:
    """
    True for private-enterprise OID branches (1.3.6.1.4.1.*).

    Trap MIB preloading only walks mib_map for these OIDs. Standard traps
    (1.3.6.1.2.1, 1.3.6.1.6.3, etc.) rely on DEFAULT_STANDARD_MIBS loaded at
    Poller startup; numeric OIDs in varbind *values* under those trees are
    still checked when they match OID_VALIDATOR.
    """
    return oid.startswith("1.3.6.1.4.1")


def _unresolved_field_name(oid: str) -> str:
    return f"{UNRESOLVED_FIELD_PREFIX}{oid}"


def _oid_tuple(oid: str):
    try:
        return tuple(int(x) for x in oid.split("."))
    except ValueError as e:
        raise SmiError(f"invalid OID {oid!r}") from e


def _mib_view_get_node_location(mib_view_controller, oid):
    get_location = getattr(mib_view_controller, "get_node_location", None)
    if get_location is not None:
        return get_location(oid)
    return mib_view_controller.getNodeLocation(oid)


def _resolve_trap_varbind(self, name: str, value):
    """Resolve a trap varbind; table instance OIDs need getNodeLocation decomposition."""
    try:
        return ObjectType(ObjectIdentity(name), value).resolveWithMib(
            self.mib_view_controller
        )
    except SmiError:
        pass

    if not OID_VALIDATOR.match(name):
        raise SmiError(f"non-numeric OID {name!r}")

    loc = None
    try:
        loc = _mib_view_get_node_location(self.mib_view_controller, _oid_tuple(name))
        mod_name, sym_name, suffix = loc
    except (SmiError, NoSuchObjectError) as e:
        raise SmiError(f"no MIB location for {name}") from e
    except (TypeError, ValueError) as e:
        raise SmiError(f"invalid MIB location tuple for {name}: {loc!r}") from e

    identity_args = [mod_name, sym_name]
    if suffix:
        identity_args.extend(suffix)
    return ObjectType(ObjectIdentity(*identity_args), value).resolveWithMib(
        self.mib_view_controller
    )


def _append_unresolved_trap_varbinds(unresolved, metrics):
    """Include varbinds that could not be translated so trap payloads are not dropped."""
    if not unresolved:
        return
    if UNRESOLVED_TRAP_GROUP_KEY not in metrics:
        metrics[UNRESOLVED_TRAP_GROUP_KEY] = {
            "metrics": {},
            "fields": {},
            "indexes": [],
        }
    fields = metrics[UNRESOLVED_TRAP_GROUP_KEY]["fields"]
    now = time.time()
    for name, value in unresolved:
        fields[_unresolved_field_name(name)] = {
            "time": now,
            "type": "f",
            "value": value_as_best(value),
            "oid": name,
        }


def _preload_trap_mibs(self, work):
    """
    Load MIB modules referenced by trap varbinds before OID translation.

    Only enterprise numeric OIDs trigger mib_map lookups here; see _is_enterprise_oid.
    """
    mibs_to_load = set()
    for varbind in work["data"]:
        for oid in _oids_for_mib_lookup(varbind):
            if not _is_enterprise_oid(oid):
                continue
            found, mib = self.is_mib_known(oid, oid, work["host"])
            if found:
                mibs_to_load.add(mib)
    new_mibs = mibs_to_load - self.already_loaded_mibs
    if new_mibs:
        self.load_mibs(new_mibs)
        self.already_loaded_mibs.update(new_mibs)


@shared_task(bind=True, base=Poller)
def trap(self, work):
    varbind_table, not_translated_oids, remaining_oids, remotemibs = [], [], [], set()
    metrics = {}
    work["host"] = format_ipv4_address(work["host"])

    _preload_trap_mibs(self, work)
    _process_work_data(self, work, varbind_table, not_translated_oids)
    unresolved = _process_remaining_oids(
        self,
        not_translated_oids,
        remotemibs,
        remaining_oids,
        work["host"],
        varbind_table,
    )
    _, _, result = self.process_snmp_data(varbind_table, metrics, work["host"])
    _append_unresolved_trap_varbinds(unresolved, result)
    if human_bool(RESOLVE_TRAP_ADDRESS):
        work["host"] = resolve_address(work["host"])
    fields = work.get("fields", None)

    return _build_result(result, work["host"], fields)


def _process_work_data(self, work, varbind_table, not_translated_oids):
    """Process the data in work to populate varbinds."""
    for w in work["data"]:
        try:
            varbind_table.append(_resolve_trap_varbind(self, w[0], w[1]))
        except SmiError:
            not_translated_oids.append((w[0], w[1]))


def _process_remaining_oids(
    self, not_translated_oids, remotemibs, remaining_oids, host, varbind_table
):
    """Process OIDs that could not be translated and add them to other oids."""
    unresolved = []
    for oid in not_translated_oids:
        found, mib = self.is_mib_known(oid[0], oid[0], host)
        if found:
            if mib not in self.already_loaded_mibs:
                remotemibs.add(mib)
            remaining_oids.append((oid[0], oid[1]))
        else:
            unresolved.append((oid[0], oid[1]))

    if remotemibs:
        self.load_mibs(remotemibs)
        self.already_loaded_mibs.update(remotemibs)
    if remaining_oids:
        unresolved.extend(_resolve_remaining_oids(self, remaining_oids, varbind_table))
    return unresolved


def _resolve_remaining_oids(self, remaining_oids, varbind_table):
    """Resolve remaining OIDs."""
    unresolved = []
    for w in remaining_oids:
        try:
            varbind_table.append(_resolve_trap_varbind(self, w[0], w[1]))
        except SmiError:
            logger.warning(f"No translation found for {w[0]}")
            unresolved.append(w)
    return unresolved


def _build_result(result, host, fields=None):
    """Build the final result dictionary."""
    result = {
        "time": time.time(),
        "result": result,
        "address": host,
        "detectchange": False,
        "sourcetype": SPLUNK_SOURCETYPE_TRAPS,
    }
    if fields:
        result["fields"] = fields
    return result


def format_ipv4_address(host: str) -> str:
    # IPv4 addresses from IPv6 socket have added ::ffff: prefix, which is removed
    if IPv6_ENABLED and "." in host:
        return host.split(":")[-1]
    return host
