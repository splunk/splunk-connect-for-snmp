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
import typing
from asyncio import Queue, QueueEmpty, TaskGroup
from collections import defaultdict
from contextlib import suppress

from pysnmp.proto.errind import EmptyResponse
from pysnmp.smi import error
from pysnmp.smi.builder import MibBuilder
from pysnmp.smi.error import SmiError
from requests import Session

from splunk_connect_for_snmp.common.collection_manager import ProfilesManager
from splunk_connect_for_snmp.inventory.loader import transform_address_to_key
from splunk_connect_for_snmp.snmp.varbinds_resolver import ProfileCollection

with suppress(ImportError, OSError):
    from dotenv import load_dotenv

    load_dotenv()

import csv
import os
import time
from io import StringIO
from typing import Any, Dict, List, Tuple, Union

import pymongo
from celery import Task
from celery.utils.log import get_task_logger
from pysnmp.hlapi.asyncio import SnmpEngine, bulk_walk_cmd, get_cmd
from pysnmp.smi import compiler, view
from pysnmp.smi.rfc1902 import ObjectIdentity, ObjectType
from requests_cache import MongoCache

from splunk_connect_for_snmp.common.hummanbool import human_bool
from splunk_connect_for_snmp.common.inventory_record import InventoryRecord
from splunk_connect_for_snmp.common.requests import CachedLimiterSession
from splunk_connect_for_snmp.snmp.auth import get_auth, setup_transport_target
from splunk_connect_for_snmp.snmp.context import get_context_data
from splunk_connect_for_snmp.snmp.exceptions import SnmpActionError

MIB_SOURCES = os.getenv("MIB_SOURCES", "https://pysnmp.github.io/mibs/asn1/@mib@")
MIB_INDEX = os.getenv("MIB_INDEX", "https://pysnmp.github.io/mibs/index.csv")
MIB_STANDARD = os.getenv("MIB_STANDARD", "https://pysnmp.github.io/mibs/standard.txt")
HOSTS_TO_IGNORE_NOT_INCREASING_OIDS = os.getenv("IGNORE_NOT_INCREASING_OIDS", "").split(
    ","
)
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "sc4snmp")
IGNORE_EMPTY_VARBINDS = human_bool(os.getenv("IGNORE_EMPTY_VARBINDS", False))
CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.yaml")
PROFILES_RELOAD_DELAY = int(os.getenv("PROFILES_RELOAD_DELAY", "60"))
UDP_CONNECTION_TIMEOUT = int(os.getenv("UDP_CONNECTION_TIMEOUT", 3))
MAX_OID_TO_PROCESS = int(os.getenv("MAX_OID_TO_PROCESS", 70))
PYSNMP_DEBUG = os.getenv("PYSNMP_DEBUG", "")
MAX_REPETITIONS = int(os.getenv("MAX_REPETITIONS", 10))
MAX_SNMP_BULK_WALK_CONCURRENCY = int(os.getenv("MAX_SNMP_BULK_WALK_CONCURRENCY", 5))

DEFAULT_STANDARD_MIBS = [
    "HOST-RESOURCES-MIB",
    "IF-MIB",
    "IP-MIB",
    "SNMPv2-MIB",
    "TCP-MIB",
    "UDP-MIB",
]

logger = get_task_logger(__name__)

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


def return_address_and_port(target):
    if ":" in target:
        address_tuple = target.rsplit(":", 1)
        return address_tuple[0], int(address_tuple[1])
    else:
        return target, 161


def is_increasing_oids_ignored(host, port):
    if (
        host in HOSTS_TO_IGNORE_NOT_INCREASING_OIDS
        or f"{host}:{port}" in HOSTS_TO_IGNORE_NOT_INCREASING_OIDS
    ):
        return True
    return False


def get_inventory(mongo_inventory, address):
    host, port = return_address_and_port(address)
    ir_doc = mongo_inventory.find_one({"address": host, "port": port})
    if ir_doc is None:
        raise ValueError(f"Inventory Doc deleted unable to complete task for {address}")
    logger.debug(f"{ir_doc}")
    ir_doc.pop("_id", None)
    return InventoryRecord(**ir_doc)


def _any_failure_happened(
    error_indication, error_status, error_index, varbinds: tuple, address, walk
) -> bool:
    """
    This function checks if any failure happened during GET or BULK operation.
    :param error_indication:
    :param error_status:
    :param error_index: index of varbind where error appeared
    :param varbinds: a sequential tuple of varbinds
    :return: if any failure happened
    """
    if error_indication:
        if isinstance(error_indication, EmptyResponse) and IGNORE_EMPTY_VARBINDS:
            return False
        raise SnmpActionError(
            f"An error of SNMP isWalk={walk} for a host {address} occurred: {error_indication}"
        )
    elif error_status:
        result = "{} at {}".format(
            error_status.prettyPrint(),
            error_index and varbinds[int(error_index) - 1][0] or "?",
        )
        raise SnmpActionError(
            f"An error of SNMP isWalk={walk} for a host {address} occurred: {result}"
        )
    return False


def is_mib_resolved(id):
    if (
        id.startswith("RFC1213-MIB::")
        or id.startswith("SNMPv2-SMI::enterprises.")
        or id.startswith("SNMPv2-SMI::mib-2")
    ):
        return False
    else:
        return True


def get_group_key(mib, oid, index) -> str:
    parts = []
    for iv in index:
        ivt = type(iv._value).__name__
        # Object Name means this is by itself
        if ivt == "ObjectName":
            parts.append(f"{ivt}={oid}")
        elif ivt == "tuple":
            ivtp = []
            for iv_tuple in iv._value:
                try:
                    ivtp.append(f"{type(iv_tuple).__name__}={str(iv_tuple._value)}")
                except Exception:
                    ivtp.append(f"{type(iv_tuple).__name__}={str(iv_tuple)}")
            parts.append(f"{ivt}={'|'.join(ivtp)}")
        else:
            parts.append(f"{ivt}={str(iv._value)}")
    return mib + "::" + ";".join(parts)


MTYPES_CC = tuple(["Counter32", "Counter64", "TimeTicks"])
MTYPES_G = tuple(
    ["Gauge32", "Gauge64", "Integer", "Integer32", "Unsigned32", "Unsigned64"]
)
MTYPES_R = tuple(["ObjectIdentifier", "ObjectIdentity"])
MTYPES = tuple(["cc", "c", "g"])


def value_as_best(value) -> Union[str, float]:
    try:
        return float(value)
    except ValueError:
        return value
    except TypeError:
        return value


def map_metric_type(t, snmp_value):
    if t in MTYPES_CC:
        metric_type = "cc"
    elif t in MTYPES_G:
        metric_type = "g"
    elif t in MTYPES_R:
        metric_type = "r"
    else:
        metric_type = "f"
    # If this claims to be a metric type but isn't a number make it a te (type error)
    if metric_type in MTYPES:
        try:
            float(snmp_value)
        except ValueError:
            metric_type = "te"
    return metric_type


def fill_empty_value(index_number, metric_value, target):
    if metric_value is None or (isinstance(metric_value, str) and not metric_value):
        if isinstance(index_number, bytes):
            try:
                metric_value = str(index_number, "utf-8")
            except UnicodeDecodeError:
                logger.error(
                    f"index_number={str(index_number)} metric_value={metric_value} target={target}"
                )
                metric_value = "sc4snmp:unconvertable"
        else:
            metric_value = index_number
    return metric_value


def extract_index_number(index):
    if not index:
        return 0
    index_number = index[0]._value
    if isinstance(index_number, typing.Tuple):
        index_number = index_number[0]
    return index_number


def extract_indexes(index):
    """
    Extracts indexes from OIDs of metrics.
    Not always MIB files are structurized the way one of the field is a meaningful index.
    :param index: pysnmp object retrieved from a device
    :return: list
    """
    indexes_to_return = []
    if not index:
        return [0]
    if isinstance(index, tuple):
        for element in index:
            if isinstance(element._value, bytes):
                element_value = ".".join(str(byte) for byte in element._value)
                indexes_to_return.append(element_value)
            elif isinstance(element._value, tuple):
                element_value = list(element)
                indexes_to_return += element_value
            else:
                indexes_to_return.append(element._value)
    return indexes_to_return


def get_max_bulk_walk_concurrency(count: int) -> int:
    """
    Return the effective bulk concurrency, Default to 5 if not set.

    :param count: Desired integer number of concurrent SNMP operations (bulk_walk_cmd)
        (count determined based on the lenght of bulk varbinds)

    :return int: The concurrency to use for SNMP operation
    """
    if count < MAX_SNMP_BULK_WALK_CONCURRENCY:
        return count
    return MAX_SNMP_BULK_WALK_CONCURRENCY


def patch_inet_address_classes(mib_builder: MibBuilder) -> bool:
    """
    Adjust InetAddress classes for compatibility with legacy length-prefixed
    OID index decoding used by earlier PySNMP versions (RFC 4001).

    ## NOTE
    In current pysmp, the INET-ADDRESS-MIB definitions for
    InetAddressIPv4, InetAddressIPv6, InetAddressIPv4z, and InetAddressIPv6z
    include a `fixed_length` attribute, e.g.:

        class InetAddressIPv4(TextualConvention, OctetString):
            subtypeSpec = OctetString.subtypeSpec + ConstraintsUnion(
                ValueSizeConstraint(4, 4),
            )
            fixed_length = 4

    Older pysnmp releases did **not** define `fixed_length`. When present,
    the SNMP `setFromName()` method takes the *fixed-length* branch:

        elif obj.is_fixed_length():
            fixed_length = obj.get_fixed_length()
            return obj.clone(tuple(value[:fixed_length])), value[fixed_length:]

    instead of the *length-prefixed* branch required by RFC 4001:

        else:
            return obj.clone(tuple(value[1:value[0]+1])), value[value[0]+1:]

    This changes how address-based table indices (e.g. **IP-MIB::ipAddressTable**)
    are parsed.

    Example:
        OID index: 1.3.6.1.2.1.4.34.1.3.1.4.127.0.0.1
        Expected:  ipAddressIfIndex.ipv4."127.0.0.1"

        Index portion: (1, 4, 127, 0, 0, 1)
        |---| |-----------|
        |        |__ Address octets
        |__ Length prefix (4)

    With `fixed_length = 4`:
        --> Parsed as (4,127,0,0) + leftover (1)
        --> Raises “Excessive instance identifier sub-OIDs left …”

    Without `fixed_length`:
        - Correctly parses (127,0,0,1) as the IPv4 address.

    Fix:
        This patch disables the `fixed_length` attribute.

    :param mib_builder: MibBuilder that has loaded INET-ADDRESS-MIB.
    :return: True if patch applied successfully, False otherwise.
    """

    try:
        (InetAddressIPv4, InetAddressIPv6, InetAddressIPv4z, InetAddressIPv6z) = (
            mib_builder.import_symbols(
                "INET-ADDRESS-MIB",
                "InetAddressIPv4",
                "InetAddressIPv6",
                "InetAddressIPv4z",
                "InetAddressIPv6z",
            )
        )

        logger.info("Applying InetAddress monkey patch for lextudio pysnmp v7.x bug...")

        classes_to_patch = [
            ("InetAddressIPv4", InetAddressIPv4),
            ("InetAddressIPv6", InetAddressIPv6),
            ("InetAddressIPv4z", InetAddressIPv4z),
            ("InetAddressIPv6z", InetAddressIPv6z),
        ]

        for class_name, cls in classes_to_patch:
            cls.fixed_length = None
            logger.info(f"Removed the problematic fixed_length attribute {class_name}")

        logger.info("All InetAddress classes successfully patched")
        return True

    except ImportError as e:
        logger.info(f"Could not import INET-ADDRESS-MIB for patching: {e}")
        return False

    except Exception as e:
        logger.info(f"Unexpected error while patching InetAddress classes: {e}")
        return False


class Poller(Task):
    def __init__(self, **kwargs):
        self.standard_mibs = []
        self.mongo_client = pymongo.MongoClient(MONGO_URI)

        if kwargs.get("no_mongo"):
            self.session = Session()
        else:
            self.session = CachedLimiterSession(
                per_second=120,
                cache_name="cache_http",
                backend=MongoCache(connection=self.mongo_client, db_name=MONGO_DB),
                expire_after=1800,
                match_headers=False,
                stale_if_error=True,
                allowable_codes=[200],
            )

        self.profiles_manager = ProfilesManager(self.mongo_client)
        self.profiles = self.profiles_manager.return_collection()
        self.profiles_collection = ProfileCollection(self.profiles)
        self.profiles_collection.process_profiles()
        self.last_modified = time.time()
        self.snmpEngine = SnmpEngine()
        self.already_loaded_mibs = set()
        self.builder = self.snmpEngine.get_mib_builder()
        self.mib_view_controller = view.MibViewController(self.builder)
        compiler.add_mib_compiler(self.builder, sources=[MIB_SOURCES])

        for mib in DEFAULT_STANDARD_MIBS:
            self.standard_mibs.append(mib)
            self.builder.load_modules(mib)

        mib_response = self.session.get(f"{MIB_INDEX}")
        self.mib_map = {}
        if mib_response.status_code == 200:
            with StringIO(mib_response.text) as index_csv:
                reader = csv.reader(index_csv)
                for each_row in reader:
                    if len(each_row) == 2:
                        self.mib_map[each_row[1]] = each_row[0]
            logger.debug(f"Loaded {len(self.mib_map.keys())} mib map entries")
        else:
            logger.error(
                f"Unable to load mib map from index http error {mib_response.status_code}"
            )

    async def do_work(
        self,
        ir: InventoryRecord,
        walk: bool = False,
        profiles: Union[List[str], None] = None,
    ):
        """
         ## NOTE
        - When a task arrived at poll queue starts with a fresh SnmpEngine (which has no transport_dispatcher
          attached), SNMP requests (get_cmd or bulk_walk_cmd or any other) run normally.
        - if a later task finds that the SnmpEngine already has a transport_dispatcher, it reuse that transport_dispatcher.
          this causes SNMP requests to hang infinite time.
        - If this hang occurs, then as per our Celery configuration, any task that
          remains in the queue longer than the default 2400s will be forcefully
          hard-timed-out and discarded.
        - The issue does not always appear on the alternate task but it may happen
          on the second, third, or any subsequent task, depending on timing and
          concurrency.

        The only way to eliminate this hang is to create new SnmpEngine for each poll task.

        """
        snmpEngine = SnmpEngine()
        retry = False
        address = transform_address_to_key(ir.address, ir.port)
        logger.info(f"Preparing task for {ir.address}")

        if time.time() - self.last_modified > PROFILES_RELOAD_DELAY or walk:
            self.profiles = self.profiles_manager.return_collection()
            self.profiles_collection.update(self.profiles)
            self.last_modified = time.time()
            logger.debug("Profiles reloaded")

        varbinds_get, get_mapping, varbinds_bulk, bulk_mapping = self.get_varbinds(
            address, walk=walk, profiles=profiles
        )

        auth_data = await get_auth(logger, ir, snmpEngine)
        context_data = get_context_data()

        transport = await setup_transport_target(ir)

        metrics: Dict[str, Any] = {}
        if not varbinds_get and not varbinds_bulk:
            logger.info(f"No work to do for {address}")
            return False, {}

        if varbinds_bulk:
            await self.run_bulk_request(
                address,
                auth_data,
                bulk_mapping,
                context_data,
                ir,
                metrics,
                transport,
                varbinds_bulk,
                walk,
            )

        if varbinds_get:
            await self.run_get_request(
                address,
                auth_data,
                context_data,
                get_mapping,
                ir,
                metrics,
                transport,
                varbinds_get,
                walk,
            )

        for group_key, metric in metrics.items():
            if "profiles" in metrics[group_key]:
                metrics[group_key]["profiles"] = ",".join(
                    metrics[group_key]["profiles"]
                )

        return retry, metrics

    async def run_get_request(
        self,
        address,
        auth_data,
        context_data,
        get_mapping,
        ir,
        metrics,
        transport,
        varbinds_get,
        walk,
    ):
        # some devices cannot process more OID than X, so it is necessary to divide it on chunks
        for varbind_chunk in self.get_varbind_chunk(varbinds_get, MAX_OID_TO_PROCESS):
            try:
                (error_indication, error_status, error_index, varbind_table) = (
                    await get_cmd(
                        SnmpEngine(),
                        auth_data,
                        transport,
                        context_data,
                        *varbind_chunk,
                        lookupMib=False,
                    )
                )
            except Exception as e:
                logger.exception(f"Error while performing get_cmd: {e}")
                return

            if not _any_failure_happened(
                error_indication,
                error_status,
                error_index,
                varbind_table,
                ir.address,
                walk,
            ):
                self.process_snmp_data(varbind_table, metrics, address, get_mapping)

    async def run_bulk_request(
        self,
        address,
        auth_data,
        bulk_mapping,
        context_data,
        ir,
        metrics,
        transport,
        varbinds_bulk,
        walk,
    ):
        """
        Perform asynchronous SNMP BULK requests on multiple varbinds with concurrency control.

        This function uses bulk_walk_cmd to asynchronously walk each SNMP varbind,
        ensuring that at most `MAX_SNMP_BULK_WALK_CONCURRENCY` walks are running concurrently.
        It processes the received SNMP data, and handles failure if any.

        :param address: IP address of the SNMP device to query
        :param auth_data: SNMP authentication data
        :param bulk_mapping: mapping dictionary to process SNMP metrics
        :param context_data: SNMP ContextData object
        :param ir: object containing SNMP device info
        :param metrics: dictionary to store metrics collected from SNMP responses
        :param transport: SNMP transport target
        :param varbinds_bulk: set of SNMP varbinds to query
        :param walk: boolean flag indicating if it is a walk operation

        :return:

        ## NOTE
        - The current `bulk_cmd` of PySNMP does not support the `lexicographicMode` option.
        As a result, the walk is not strictly confined to the requested varBind subtree and may go beyond the requested OID subtree,
        with a high chance of duplicate OIDs.

        - Used `bulk_walk_cmd` of pysnmp, which supports `lexicographicMode` and walks a subtree correctly,
        but handles only one varBind at a time.
        """

        async def _walk_single_varbind(varbind, wid):
            """
            Asynchronously walk a single SNMP varbind and process the results.
            :param varbind: SNMP ObjectType varbind to be walked
            :return:
            """
            try:
                async for (
                    error_indication,
                    error_status,
                    error_index,
                    varbind_table,
                ) in bulk_walk_cmd(
                    SnmpEngine(),
                    auth_data,
                    transport,
                    context_data,
                    0,
                    MAX_REPETITIONS,
                    varbind,
                    lexicographicMode=False,
                    lookupMib=False,
                    ignoreNonIncreasingOid=is_increasing_oids_ignored(
                        ir.address, ir.port
                    ),
                ):
                    if not _any_failure_happened(
                        error_indication,
                        error_status,
                        error_index,
                        varbind_table,
                        ir.address,
                        walk,
                    ):
                        _, tmp_mibs, _ = self.process_snmp_data(
                            varbind_table, metrics, address, bulk_mapping
                        )
                        if tmp_mibs:
                            self.load_mibs(tmp_mibs)
                            self.process_snmp_data(
                                varbind_table, metrics, address, bulk_mapping
                            )
            except Exception as e:
                logger.exception(f"Error while performing bulk_walk_cmd: {e}")

        # Preparing the queue for bulk request
        bulk_queue: Queue[tuple[int, ObjectType]] = Queue()
        for _wid, _varbind in enumerate(varbinds_bulk, start=1):
            bulk_queue.put_nowait((_wid, _varbind))

        async def _worker(worker_id: int):
            """
            Worker coroutine that continuously fetches tasks from the bulk_queue and
            executes SNMP walks using _walk_single_varbind.
            :param worker_id: integer ID of the worker

            :return:
            """
            while True:
                try:
                    _wid, _varbind = bulk_queue.get_nowait()
                except QueueEmpty:
                    # Queue is empty indicating that all the varbinds proceed for the poll/walk task.
                    logger.debug(
                        f"BulkQueue worker-{worker_id} found no tasks in the queue and is exiting."
                    )
                    break
                except Exception as e:
                    logger.error(
                        f"BulkQueue worker-{worker_id} encountered an error: {e}."
                    )
                    break

                logger.debug(f"BulkQueue worker-{worker_id} picking up task-{_wid}")
                await _walk_single_varbind(_varbind, worker_id)
                bulk_queue.task_done()
                logger.debug(f"BulkQueue worker-{worker_id} completed task-{_wid}")

        try:
            async with TaskGroup() as tg:
                for wid in range(
                    1, get_max_bulk_walk_concurrency(len(varbinds_bulk)) + 1
                ):
                    tg.create_task(_worker(wid))
        except ExceptionGroup as eg:
            for e in eg.exceptions:
                raise e

    def get_varbind_chunk(self, lst, n):
        for i in range(0, len(lst), n):
            yield lst[i : i + n]

    def load_mibs(self, mibs: List[str]) -> None:
        logger.info(f"loading mib modules {mibs}")
        for mib in mibs:
            if mib:
                try:
                    self.builder.load_modules(mib)
                except Exception as e:
                    logger.warning(f"Error loading mib for {mib}, {e}")

    def is_mib_known(self, id: str, oid: str, target: str) -> Tuple[bool, str]:
        oid_list = tuple(oid.split("."))
        # if oid match enterprise, then search should stop if there is no match to vendor
        start = 6 if oid.startswith("1.3.6.1.4.1") else 5
        for i in range(len(oid_list), start, -1):
            oid_to_check = ".".join(oid_list[:i])
            if oid_to_check in self.mib_map:
                mib = self.mib_map[oid_to_check]
                logger.debug(f"found {mib} for {id} based on {oid_to_check}")
                return True, mib
        logger.warning(f"no mib found {id} based on {oid} from {target}")
        return False, ""

    def get_varbinds(self, address, walk=False, profiles=[]):
        varbinds_bulk = set()
        varbinds_get = set()
        get_mapping = {}
        bulk_mapping = {}
        if walk and not profiles:
            varbinds_bulk.add(ObjectType(ObjectIdentity("1.3.6")))
            return varbinds_get, get_mapping, varbinds_bulk, bulk_mapping

        joined_profile_object = self.profiles_collection.get_polling_info_from_profiles(
            profiles, walk
        )
        if joined_profile_object:
            mib_families = joined_profile_object.get_mib_families()
            mib_files_to_load = [
                mib_family
                for mib_family in mib_families
                if mib_family not in self.already_loaded_mibs
            ]
            if mib_files_to_load:
                self.load_mibs(mib_files_to_load)
            (
                varbinds_get,
                get_mapping,
                varbinds_bulk,
                bulk_mapping,
            ) = joined_profile_object.return_mapping_and_varbinds()
        logger.debug(f"host={address} varbinds_get={varbinds_get}")
        logger.debug(f"host={address} get_mapping={get_mapping}")
        logger.debug(f"host={address} varbinds_bulk={varbinds_bulk}")
        logger.debug(f"host={address} bulk_mapping={bulk_mapping}")
        return varbinds_get, get_mapping, varbinds_bulk, bulk_mapping

    def process_snmp_data(self, varbind_table, metrics, target, mapping={}):
        retry = False
        remotemibs = []
        for varbind in varbind_table:

            index, metric, mib, oid, varbind_id = self.init_snmp_data(varbind)

            if is_mib_resolved(varbind_id):
                group_key = get_group_key(mib, oid, index)
                self.handle_groupkey_without_metrics(group_key, index, mapping, metrics)
                try:

                    metric_type, metric_value = self.set_metrics_index(
                        index, target, varbind
                    )

                    profile = self.set_profile_name(mapping, metric, mib, varbind_id)
                    if metric_value == "No more variables left in this MIB View":
                        continue

                    self.handle_metrics(
                        group_key,
                        metric,
                        metric_type,
                        metric_value,
                        metrics,
                        mib,
                        oid,
                        profile,
                    )
                except Exception:
                    logger.exception(
                        f"Exception processing data from {target} {varbind}"
                    )
            else:
                found = self.find_new_mibs(oid, remotemibs, target, varbind_id)
                if found:
                    retry = True
                    break

        return retry, remotemibs, metrics

    def find_new_mibs(self, oid, remotemibs, target, varbind_id):
        found, mib = self.is_mib_known(varbind_id, oid, target)
        if mib and mib not in remotemibs:
            remotemibs.append(mib)
        return found

    def handle_metrics(
        self, group_key, metric, metric_type, metric_value, metrics, mib, oid, profile
    ):
        if metric_type in MTYPES and (isinstance(metric_value, float)):
            metrics[group_key]["metrics"][f"{mib}.{metric}"] = {
                "time": time.time(),
                "type": metric_type,
                "value": metric_value,
                "oid": oid,
            }
            if profile and profile not in metrics[group_key]["profiles"]:
                metrics[group_key]["profiles"].append(profile)
        else:
            metrics[group_key]["fields"][f"{mib}.{metric}"] = {
                "time": time.time(),
                "type": metric_type,
                "value": metric_value,
                "oid": oid,
            }

    def set_profile_name(self, mapping, metric, mib, varbind_id):
        """
        Finds the profile named based on the passed data.
        """
        profile = None
        if mapping:
            profile = mapping.get(
                varbind_id.replace('"', ""),
                mapping.get(f"{mib}::{metric}", mapping.get(mib)),
            )
            # when varbind name differs from mib-family,
            # we are checking if there's any key that includes this mib to get profile
            profile = self.match_mapping_to_profile(mapping, mib, profile)
            profile = self.clean_profile_name(profile)
        return profile

    def clean_profile_name(self, profile):
        if profile and "__" in profile:
            profile = profile.split("__")[0]
        return profile

    def match_mapping_to_profile(self, mapping, mib, profile):
        if not profile:
            key = [prof for mib_map, prof in mapping.items() if mib in mib_map]
            if key:
                profile = key[0]
        return profile

    def set_metrics_index(self, index, target, varbind):
        snmp_val = varbind[1]
        snmp_type = type(snmp_val).__name__
        metric_type = map_metric_type(snmp_type, snmp_val)
        metric_value = value_as_best(snmp_val.prettyPrint())
        index_number = extract_index_number(index)
        metric_value = fill_empty_value(index_number, metric_value, target)
        return metric_type, metric_value

    def handle_groupkey_without_metrics(self, group_key, index, mapping, metrics):
        if group_key not in metrics:
            indexes = extract_indexes(index)
            metrics[group_key] = {
                "metrics": {},
                "fields": {},
                "indexes": indexes,
            }
            if mapping:
                metrics[group_key]["profiles"] = []

    def init_snmp_data(self, varbind):
        """
        Extract SNMP varbind information in a way that preserves compatibility with
        older PySNMP behavior while avoiding changes to the underlying library.

        :param varbind: ObjectType

        :return: A resolved index, metric, mib, oid, varbind_id

        ## NOTE
        - In old fork of pysnmp, calling `getMibSymbol()` and `prettyPrint()` on
        a varbind returned fully resolved MIB names, variable names, and indices.

        - In lextudio's pysnmp, `get_mib_symbol()` and `prettyPrint()`
        by default may return partially resolved names as snmp request it self not
        resolved it fully, unless `resolve_with_mib()` is explicitly called.
        This is why `metric` and `varbind_id` appear different from older versions.
        """
        oid = str(varbind[0])

        try:
            resolved_oid = ObjectIdentity(oid).resolve_with_mib(
                self.mib_view_controller
            )
            mib, metric, index = resolved_oid.get_mib_symbol()
            varbind_id = resolved_oid.prettyPrint()
        except SmiError as se:
            logger.info(f"===> SmiError for oid={oid}: {se} <===")
            patch_inet_address_classes(self.builder)
            resolved_oid = ObjectIdentity(oid).resolve_with_mib(
                self.mib_view_controller
            )
            mib, metric, index = resolved_oid.get_mib_symbol()
            varbind_id = resolved_oid.prettyPrint()
            logger.info(
                f"===== {mib}, oid={oid}, varbind_id={varbind_id}, metric={metric} val={varbind[1]} ====="
            )

        return index, metric, mib, oid, varbind_id
