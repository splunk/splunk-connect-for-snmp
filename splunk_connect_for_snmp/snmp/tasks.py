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

from pyasn1.type.base import AbstractSimpleAsn1Item
from pysnmp.proto import rfc1902 as snmp_rfc1902
from pysnmp.proto import rfc1905 as snmp_rfc1905
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
from splunk_connect_for_snmp.snmp.manager import (
    Poller,
    get_inventory,
    is_mib_resolved,
    value_as_best,
)
from splunk_connect_for_snmp.snmp.trap_varbind_limit import (
    limit_trap_varbind_pairs,
    log_trap_varbind_limit_config,
)

logger = get_task_logger(__name__)

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "sc4snmp")
CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.yaml")
WALK_RETRY_MAX_INTERVAL = int(os.getenv("WALK_RETRY_MAX_INTERVAL", "180"))
WALK_MAX_RETRIES = int(os.getenv("WALK_MAX_RETRIES", "5"))
SPLUNK_SOURCETYPE_TRAPS = os.getenv("SPLUNK_SOURCETYPE_TRAPS", "sc4snmp:traps")
OID_VALIDATOR = re.compile(r"^([0-2])((\.0)|(\.[1-9]\d*))*$")
_INTEGER_STRING = re.compile(r"^-?\d+$")
_STRING_SYNTAX_NAMES = frozenset(
    {"OctetString", "Opaque", "IpAddress", "DisplayString", "PhysAddress"}
)
_INTEGER_SYNTAX_NAMES = frozenset(
    {
        "Integer",
        "Integer32",
        "Counter32",
        "Counter64",
        "Gauge32",
        "Unsigned32",
        "TimeTicks",
        "ZeroBasedCounter64",
        "CounterBasedGauge64",
    }
)
UNRESOLVED_TRAP_GROUP_KEY = "sc4snmp::unresolved"
UNRESOLVED_FIELD_PREFIX = "unresolved::"
_TRAP_MIB_RETRY_MAX = 5
RESOLVE_TRAP_ADDRESS = os.getenv("RESOLVE_TRAP_ADDRESS", "false")
INCLUDE_UNRESOLVED_TRAP_VARBINDS = human_bool(
    os.getenv("INCLUDE_UNRESOLVED_TRAP_VARBINDS", "false").lower()
)
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


def _value_for_trap_resolve(value):
    """Value ObjectType.resolveWithMib() accepts; empty strings cannot be cast."""
    if isinstance(value, AbstractSimpleAsn1Item):
        return value
    if isinstance(value, str) and value.strip() == "":
        return snmp_rfc1905.unSpecified
    return value


def _mib_syntax_class(mib_node):
    if mib_node is None or not hasattr(mib_node, "getSyntax"):
        return None
    try:
        return mib_node.getSyntax()
    except Exception as exc:
        logger.debug("MIB getSyntax failed for %s: %s", mib_node, exc)
        return None


def _coerce_trap_varbind_value(value, mib_node=None):
    """
    Build an SNMP value ObjectType.resolveWithMib() accepts.

    NOTIFICATION-TYPE nodes are not MibScalar/MibTableColumn; pysnmp only marks
    ObjectType resolved when the value is already an ASN.1 type. Plain Python
    scalars (e.g. snmpTrapOID varbind value 0) must be wrapped.
    """
    if isinstance(value, AbstractSimpleAsn1Item):
        return value
    syntax = _mib_syntax_class(mib_node)
    if syntax is not None:
        try:
            return syntax.clone(value)
        except Exception as exc:
            logger.debug("MIB syntax clone failed for %s: %s", mib_node, exc)
    if isinstance(value, bool):
        return snmp_rfc1902.Integer(int(value))
    if isinstance(value, (int, float)):
        return snmp_rfc1902.Integer(int(value))
    if isinstance(value, str):
        if value == "":
            return value
        syntax_name = getattr(syntax, "__name__", "") if syntax is not None else ""
        if syntax_name in _STRING_SYNTAX_NAMES:
            return value
        if syntax_name in _INTEGER_SYNTAX_NAMES and _INTEGER_STRING.match(value):
            return snmp_rfc1902.Integer(int(value))
        if syntax is None and _INTEGER_STRING.match(value):
            return snmp_rfc1902.Integer(int(value))
        return value
    return value


def _is_notification_mib_node(mib_node) -> bool:
    return mib_node is not None and mib_node.__class__.__name__ == "NotificationType"


def _object_type_from_resolved_identity(mib_view_controller, identity, value):
    """
    Resolve NOTIFICATION-TYPE varbinds (e.g. snmpTrapOID) via ObjectIdentity first.

    Plain Python values cannot be passed to ObjectType.resolveWithMib() for
    notifications; they must be wrapped as ASN.1 types after identity resolution.
    """
    if isinstance(identity, str):
        resolved_identity = ObjectIdentity(identity).resolveWithMib(mib_view_controller)
    else:
        resolved_identity = ObjectIdentity(*identity).resolveWithMib(
            mib_view_controller
        )
    mib_node = resolved_identity.getMibNode()
    if not _is_notification_mib_node(mib_node):
        raise SmiError(f"{identity!r} is not a NOTIFICATION-TYPE")
    return ObjectType(
        resolved_identity, _coerce_trap_varbind_value(value, mib_node)
    ).resolveWithMib(mib_view_controller)


def _resolve_trap_varbind(self, name: str, value):
    """Resolve a trap varbind; table instance OIDs need getNodeLocation decomposition."""
    resolve_value = _value_for_trap_resolve(value)
    try:
        return ObjectType(ObjectIdentity(name), resolve_value).resolveWithMib(
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
    try:
        return ObjectType(ObjectIdentity(*identity_args), resolve_value).resolveWithMib(
            self.mib_view_controller
        )
    except SmiError:
        pass

    try:
        return _object_type_from_resolved_identity(
            self.mib_view_controller, identity_args, resolve_value
        )
    except SmiError as e:
        raise SmiError(f"no MIB location for {name}") from e


def _collect_processed_trap_oids(metrics):
    processed = set()
    for group in metrics.values():
        if not isinstance(group, dict):
            continue
        for section in ("fields", "metrics"):
            for item in group.get(section, {}).values():
                if not isinstance(item, dict):
                    continue
                oid = item.get("oid")
                if oid:
                    processed.add(oid)
    return processed


def _varbind_table_value(varbind):
    try:
        return varbind[1].prettyPrint()
    except AttributeError:
        return varbind[1]


def _unprocessed_trap_varbinds(varbind_table, metrics):
    """
    Varbinds resolved into varbind_table but skipped by process_snmp_data (e.g. first
    trap before MIB symbols are fully qualified) are not in unresolved; collect them
    so they can still be forwarded when INCLUDE_UNRESOLVED_TRAP_VARBINDS is enabled.
    """
    processed = _collect_processed_trap_oids(metrics)
    unprocessed = []
    for varbind in varbind_table:
        oid = str(varbind[0].getOid())
        if oid not in processed:
            unprocessed.append((oid, _varbind_table_value(varbind)))
    return unprocessed


def _merge_unresolved_trap_varbinds(*sources):
    merged = []
    seen = set()
    for source in sources:
        for name, value in source:
            if name in seen:
                continue
            seen.add(name)
            merged.append((name, value))
    return merged


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


def _resolve_work_varbinds(self, work_data):
    """Resolve every trap varbind; return table and pairs that still fail translation."""
    varbind_table = []
    unresolved = []
    for name, value in work_data:
        try:
            varbind_table.append(_resolve_trap_varbind(self, name, value))
        except SmiError:
            unresolved.append((name, value))
    return varbind_table, unresolved


def _varbind_table_has_unresolved_symbols(varbind_table) -> bool:
    """True if any resolved varbind still uses a placeholder MIB name (e.g. enterprises.*)."""
    for varbind in varbind_table:
        try:
            varbind_id = varbind[0].prettyPrint()
        except AttributeError:
            continue
        if not is_mib_resolved(varbind_id):
            return True
    return False


def _re_resolve_trap_work_if_needed(self, work_data, varbind_table, unresolved):
    """
    Re-resolve the full trap when varbinds look resolved but use placeholder symbols.

    This covers partial first-pass success before MIB modules are usable in the view.
    """
    if not _varbind_table_has_unresolved_symbols(varbind_table):
        return varbind_table, unresolved
    new_table, still_unresolved = _resolve_work_varbinds(self, work_data)
    return new_table, _merge_unresolved_trap_varbinds(unresolved, still_unresolved)


def _load_new_trap_mibs(self, mib_names) -> bool:
    """Load MIB modules not already in already_loaded_mibs; return True if any were loaded."""
    new_mibs = set(mib_names) - self.already_loaded_mibs
    if not new_mibs:
        return False
    loaded = self.load_mibs(list(new_mibs))
    self.already_loaded_mibs.update(loaded)
    return bool(loaded)


def _process_trap_metrics(self, work_data, varbind_table, metrics, host):
    """
    Build trap metrics from resolved varbinds, loading MIBs discovered during processing.

    Re-resolves all varbinds only when process_snmp_data triggers a new MIB load.
    """
    result = {}
    for _ in range(_TRAP_MIB_RETRY_MAX):
        retry, remotemibs, result = self.process_snmp_data(
            varbind_table, metrics, host
        )
        if not retry or not remotemibs:
            break
        if _load_new_trap_mibs(self, remotemibs):
            varbind_table, _ = _resolve_work_varbinds(self, work_data)
        else:
            # MIB names are known and already loaded; re-resolve once and re-process.
            varbind_table, _ = _resolve_work_varbinds(self, work_data)
            _, _, result = self.process_snmp_data(varbind_table, metrics, host)
            break
    if not result and varbind_table:
        logger.warning(
            "Trap varbinds resolved but produced no metrics for %s (%d varbinds)",
            host,
            len(varbind_table),
        )
    return result


def _preload_trap_mibs(self, work) -> bool:
    """
    Load MIB modules referenced by trap varbinds before OID translation.

    Only enterprise numeric OIDs trigger mib_map lookups here; see _is_enterprise_oid.
    Returns True if any new MIB module was loaded.
    """
    mibs_to_load = set()
    for varbind in work["data"]:
        for oid in _oids_for_mib_lookup(varbind):
            if not _is_enterprise_oid(oid):
                continue
            found, mib = self.is_mib_known(oid, oid, work["host"])
            if found:
                mibs_to_load.add(mib)
    return _load_new_trap_mibs(self, mibs_to_load)


def _retry_trap_varbinds_after_mib_load(
    self, work_data, host, not_translated, varbind_table
):
    """
    Resolve varbinds that failed the first pass.

    If loading deferred MIBs succeeds, re-resolve the full trap; otherwise resolve only
    the failed pairs and append them to varbind_table.
    """
    unresolved = []
    remotemibs = set()
    retry_pairs = []
    for name, value in not_translated:
        found, mib = self.is_mib_known(name, name, host)
        if found:
            remotemibs.add(mib)
            retry_pairs.append((name, value))
        else:
            unresolved.append((name, value))

    if remotemibs and _load_new_trap_mibs(self, remotemibs):
        varbind_table, still_unresolved = _resolve_work_varbinds(self, work_data)
        return varbind_table, _merge_unresolved_trap_varbinds(unresolved, still_unresolved)

    for name, value in retry_pairs:
        try:
            varbind_table.append(_resolve_trap_varbind(self, name, value))
        except SmiError:
            logger.warning(f"No translation found for {name}")
            unresolved.append((name, value))
    return varbind_table, unresolved


@shared_task(bind=True, base=Poller)
def trap(self, work):
    log_trap_varbind_limit_config(logger)
    metrics = {}
    work["host"] = format_ipv4_address(work["host"])
    work["data"] = limit_trap_varbind_pairs(
        work.get("data", []), log=logger, source=work["host"]
    )

    mibs_loaded = _preload_trap_mibs(self, work)
    if mibs_loaded:
        varbind_table, unresolved = _resolve_work_varbinds(self, work["data"])
    else:
        varbind_table, not_translated = [], []
        for name, value in work["data"]:
            try:
                varbind_table.append(_resolve_trap_varbind(self, name, value))
            except SmiError:
                not_translated.append((name, value))
        if not_translated:
            varbind_table, unresolved = _retry_trap_varbinds_after_mib_load(
                self, work["data"], work["host"], not_translated, varbind_table
            )
        else:
            unresolved = []

    varbind_table, unresolved = _re_resolve_trap_work_if_needed(
        self, work["data"], varbind_table, unresolved
    )

    result = _process_trap_metrics(
        self, work["data"], varbind_table, metrics, work["host"]
    )
    if INCLUDE_UNRESOLVED_TRAP_VARBINDS:
        unprocessed = _unprocessed_trap_varbinds(varbind_table, result)
        combined = _merge_unresolved_trap_varbinds(unresolved, unprocessed)
        _append_unresolved_trap_varbinds(combined, result)
    if human_bool(RESOLVE_TRAP_ADDRESS):
        work["host"] = resolve_address(work["host"])
    fields = work.get("fields", None)

    return _build_result(result, work["host"], fields)


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
