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

from pysnmp.proto.errind import EmptyResponse
from pysnmp.smi import error
from requests import Session

from splunk_connect_for_snmp.common.collection_manager import ProfilesManager
from splunk_connect_for_snmp.inventory.loader import transform_address_to_key
from splunk_connect_for_snmp.snmp.varbinds_resolver import ProfileCollection

try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass
import csv
import os
import time
from io import StringIO
from typing import Any, Dict, List, Tuple, Union

import pymongo
from celery import Task
from celery.utils.log import get_task_logger
from pysnmp.hlapi import SnmpEngine, UdpTransportTarget, bulkCmd, getCmd
from pysnmp.smi import compiler, view
from pysnmp.smi.rfc1902 import ObjectIdentity, ObjectType
from requests_cache import MongoCache

from splunk_connect_for_snmp.common.hummanbool import human_bool
from splunk_connect_for_snmp.common.inventory_record import InventoryRecord
from splunk_connect_for_snmp.common.requests import CachedLimiterSession
from splunk_connect_for_snmp.snmp.auth import GetAuth
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

DEFAULT_STANDARD_MIBS = [
    "HOST-RESOURCES-MIB",
    "IF-MIB",
    "IP-MIB",
    "SNMPv2-MIB",
    "TCP-MIB",
    "UDP-MIB",
]
logger = get_task_logger(__name__)


def return_address_and_port(target):
    if ":" in target:
        address_tuple = target.split(":")
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
    error_indication, error_status, error_index, var_binds: list, address, walk
) -> bool:
    """
    This function checks if any failure happened during GET or BULK operation.
    @param error_indication:
    @param error_status:
    @param error_index: index of varbind where error appeared
    @param var_binds: list of varbinds
    @return: if any failure happened
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
            error_index and var_binds[int(error_index) - 1][0] or "?",
        )
        raise SnmpActionError(
            f"An error of SNMP isWalk={walk} for a host {address} occurred: {result}"
        )
    return False


def isMIBResolved(id):
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
                except:
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


def valueAsBest(value) -> Union[str, float]:
    try:
        return float(value)
    except:
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
        except:
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


def extract_index_oid_part(varBind):
    """
    Extracts index from OIDs of metrics.
    Not always MIB files are structurized the way one of the field is a meaningful index.
    https://stackoverflow.com/questions/58886693/how-to-standardize-oid-index-retrieval-in-pysnmp
    :param varBind: pysnmp object retrieved from a device
    :return: str
    """
    object_identity, _ = varBind
    mib_node = object_identity.getMibNode()
    object_instance_oid = object_identity.getOid()
    object_oid = mib_node.getName()
    index_part = object_instance_oid[len(object_oid) :]
    return str(index_part)


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
        self.builder = self.snmpEngine.getMibBuilder()
        self.mib_view_controller = view.MibViewController(self.builder)
        compiler.addMibCompiler(self.builder, sources=[MIB_SOURCES])

        for mib in DEFAULT_STANDARD_MIBS:
            self.standard_mibs.append(mib)
            self.builder.loadModules(mib)

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
                f"Unable to load mib map from index http error {self.mib_response.status_code}"
            )

    def do_work(
        self,
        ir: InventoryRecord,
        walk: bool = False,
        profiles: List[str] = None,
    ):
        retry = False
        address = transform_address_to_key(ir.address, ir.port)

        if time.time() - self.last_modified > PROFILES_RELOAD_DELAY or walk:
            self.profiles = self.profiles_manager.return_collection()
            self.profiles_collection.update(self.profiles)
            self.last_modified = time.time()
            logger.debug("Profiles reloaded")

        varbinds_get, get_mapping, varbinds_bulk, bulk_mapping = self.get_var_binds(
            address, walk=walk, profiles=profiles
        )

        authData = GetAuth(logger, ir, self.snmpEngine)
        contextData = get_context_data()

        transport = UdpTransportTarget(
            (ir.address, ir.port), timeout=UDP_CONNECTION_TIMEOUT
        )

        metrics: Dict[str, Any] = {}
        if not varbinds_get and not varbinds_bulk:
            logger.info(f"No work to do for {address}")
            return False, {}

        if varbinds_bulk:

            for (errorIndication, errorStatus, errorIndex, varBindTable,) in bulkCmd(
                self.snmpEngine,
                authData,
                transport,
                contextData,
                1,
                10,
                *varbinds_bulk,
                lexicographicMode=False,
                ignoreNonIncreasingOid=is_increasing_oids_ignored(ir.address, ir.port),
            ):
                if not _any_failure_happened(
                    errorIndication,
                    errorStatus,
                    errorIndex,
                    varBindTable,
                    ir.address,
                    walk,
                ):
                    tmp_retry, tmp_mibs, _ = self.process_snmp_data(
                        varBindTable, metrics, address, bulk_mapping
                    )
                    if tmp_mibs:
                        self.load_mibs(tmp_mibs)
                        self.process_snmp_data(
                            varBindTable, metrics, address, bulk_mapping
                        )

        if varbinds_get:
            for (errorIndication, errorStatus, errorIndex, varBindTable,) in getCmd(
                self.snmpEngine, authData, transport, contextData, *varbinds_get
            ):
                if not _any_failure_happened(
                    errorIndication,
                    errorStatus,
                    errorIndex,
                    varBindTable,
                    ir.address,
                    walk,
                ):
                    self.process_snmp_data(varBindTable, metrics, address, get_mapping)

        for group_key, metric in metrics.items():
            if "profiles" in metrics[group_key]:
                metrics[group_key]["profiles"] = ",".join(
                    metrics[group_key]["profiles"]
                )

        return retry, metrics

    def load_mibs(self, mibs: List[str]) -> None:
        logger.info(f"loading mib modules {mibs}")
        for mib in mibs:
            if mib:
                try:
                    self.builder.loadModules(mib)
                except Exception as e:
                    logger.warning(f"Error loading mib for {mib}, {e}")

    def is_mib_known(self, id: str, oid: str, target: str) -> Tuple[bool, str]:

        oid_list = tuple(oid.split("."))

        start = 5
        for i in range(len(oid_list), start, -1):
            oid_to_check = ".".join(oid_list[:i])
            if oid_to_check in self.mib_map:
                mib = self.mib_map[oid_to_check]
                logger.debug(f"found {mib} for {id} based on {oid_to_check}")
                return True, mib
        logger.warning(f"no mib found {id} based on {oid} from {target}")
        return False, ""

    def get_var_binds(self, address, walk=False, profiles=[]):
        varbinds_bulk = set()
        if walk and not profiles:
            varbinds_bulk.add(ObjectType(ObjectIdentity("1.3.6")))
            return set(), {}, varbinds_bulk, {}

        joined_profile_object = self.profiles_collection.get_profiles(profiles, walk)
        mib_families = joined_profile_object.get_mib_families()
        mib_files_to_load = [mib_family for mib_family in mib_families if mib_family not in self.already_loaded_mibs]
        if mib_files_to_load:
            self.load_mibs(mib_files_to_load)
        varbinds_get, get_mapping, varbinds_bulk, bulk_mapping = joined_profile_object.return_mapping_and_varbinds()
        logger.debug(f"host={address} varbinds_get={varbinds_get}")
        logger.debug(f"host={address} get_mapping={get_mapping}")
        logger.debug(f"host={address} varbinds_bulk={varbinds_bulk}")
        logger.debug(f"host={address} bulk_mapping={bulk_mapping}")
        return varbinds_get, get_mapping, varbinds_bulk, bulk_mapping

    def process_snmp_data(self, varBindTable, metrics, target, mapping={}):
        i = 0
        retry = False
        remotemibs = []
        for varBind in varBindTable:
            i += 1
            mib, metric, index = varBind[0].getMibSymbol()

            id = varBind[0].prettyPrint()
            oid = str(varBind[0].getOid())

            if isMIBResolved(id):
                group_key = get_group_key(mib, oid, index)
                if group_key not in metrics:
                    metrics[group_key] = {
                        "metrics": {},
                        "fields": {},
                    }
                    if mapping:
                        metrics[group_key]["profiles"] = []
                try:

                    snmp_val = varBind[1]
                    snmp_type = type(snmp_val).__name__

                    metric_type = map_metric_type(snmp_type, snmp_val)
                    metric_value = valueAsBest(snmp_val.prettyPrint())

                    index_number = extract_index_number(index)
                    oid_index_part = extract_index_oid_part(varBind)
                    metric_value = fill_empty_value(index_number, metric_value, target)

                    profile = None
                    if mapping:
                        profile = mapping.get(
                            f"{mib}:{metric}:{index_number}",
                            mapping.get(f"{mib}:{metric}", mapping.get(mib)),
                        )
                    if metric_value == "No more variables left in this MIB View":
                        continue

                    if metric_type in MTYPES and (isinstance(metric_value, float)):
                        metrics[group_key]["metrics"][f"{mib}.{metric}"] = {
                            "time": time.time(),
                            "type": metric_type,
                            "value": metric_value,
                            "index": oid_index_part,
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
                except:
                    logger.exception(
                        f"Exception processing data from {target} {varBind}"
                    )
            else:
                found, mib = self.is_mib_known(id, oid, target)
                if mib and mib not in remotemibs:
                    remotemibs.append(mib)
                if found:
                    retry = True
                    break

        return retry, remotemibs, metrics
