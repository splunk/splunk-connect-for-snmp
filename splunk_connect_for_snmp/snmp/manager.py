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

try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass
import csv
import os
import time
from io import StringIO
from typing import List, Union

import pymongo
from celery import Task
from celery.utils.log import get_task_logger
from pysnmp.hlapi import SnmpEngine, UdpTransportTarget, bulkCmd, getCmd
from pysnmp.smi import compiler, view
from pysnmp.smi.rfc1902 import ObjectIdentity, ObjectType
from requests_cache import MongoCache

from splunk_connect_for_snmp.common.inventory_record import (
    InventoryRecord,
)
from splunk_connect_for_snmp.common.profiles import load_profiles
from splunk_connect_for_snmp.common.requests import CachedLimiterSession
from splunk_connect_for_snmp.snmp.auth import GetAuth
from splunk_connect_for_snmp.snmp.context import getContextData
from splunk_connect_for_snmp.snmp.exceptions import SnmpActionError

MIB_SOURCES = os.getenv("MIB_SOURCES", "https://pysnmp.github.io/mibs/asn1/@mib@")
MIB_INDEX = os.getenv("MIB_INDEX", "https://pysnmp.github.io/mibs/index.csv")
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "sc4snmp")
CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.yaml")

logger = get_task_logger(__name__)


def getInventory(mongo_inventory, address):
    ir_doc = mongo_inventory.find_one({"address": address})
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
MTYPES_C = tuple()
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
    elif t in MTYPES_C:
        metric_type = "c"
    elif t in MTYPES_G:
        metric_type = "g"
    elif t in MTYPES_R:
        metric_type = "r"
    else:
        metric_type = "f"
    # If this claims to be a metic type but isn't a number make it a te (type error)
    if metric_type in MTYPES:
        try:
            float(snmp_value)
        except:
            metric_type = "te"
    return metric_type


def fill_empty_value(index_number, metric_value):
    if metric_value is None or (isinstance(metric_value, str) and not metric_value):
        if isinstance(index_number, bytes):
            metric_value = str(index_number, 'utf-8')
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


class Poller(Task):
    def __init__(self):

        self.mongo_client = pymongo.MongoClient(MONGO_URI)

        self.session = CachedLimiterSession(
            per_second=120,
            cache_name="cache_http",
            backend=MongoCache(connection=self.mongo_client, db_name=MONGO_DB),
            expire_after=1800,
            # logger=
            match_headers=False,
            stale_if_error=True,
            allowable_codes=[200],
        )

        self.profiles = load_profiles()

        self.snmpEngine = SnmpEngine()
        self.builder = self.snmpEngine.getMibBuilder()
        self.mib_view_controller = view.MibViewController(self.builder)
        compiler.addMibCompiler(self.builder, sources=[MIB_SOURCES])
        for mib in [
            "HOST-RESOURCES-MIB",
            # "IANAifType-MIB",
            "IF-MIB",
            "IP-MIB",
            # "RFC1389-MIB",
            "SNMPv2-MIB",
            # "UCD-SNMP-MIB",
            "TCP-MIB",
            "UDP-MIB",
        ]:
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

    def dowork(self, address: str, walk: bool = False, profiles: List[str] = None):
        result = {}

        mongo_client = pymongo.MongoClient(MONGO_URI)
        mongo_db = mongo_client[MONGO_DB]
        mongo_inventory = mongo_db.inventory

        ir = getInventory(mongo_inventory, address)

        varbinds_get, get_mapping, varbinds_bulk, bulk_mapping = self.getVarBinds(
            walk=walk, profiles=profiles
        )

        authData = GetAuth(logger, ir, self.snmpEngine)
        contextData = getContextData(logger, ir)

        transport = UdpTransportTarget((ir.address, ir.port))

        metrics = {}
        retry = False
        if len(varbinds_get) == 0 and len(varbinds_bulk) == 0:
            logger.info("No work to do")
            return False, {}

        if len(varbinds_bulk) > 0:

            for (errorIndication, errorStatus, errorIndex, varBindTable,) in bulkCmd(
                self.snmpEngine,
                authData,
                transport,
                contextData,
                0,
                50,
                *varbinds_bulk,
                lexicographicMode=False,
            ):
                if not _any_failure_happened(
                    errorIndication,
                    errorStatus,
                    errorIndex,
                    varBindTable,
                    ir.address,
                    walk,
                ):
                    tmp_retry, tmp_mibs = self.process_snmp_data(
                        varBindTable, metrics, bulk_mapping
                    )
                    if tmp_mibs:
                        self.load_mibs(tmp_mibs)
                    if tmp_retry:
                        retry = True

        if len(varbinds_get) > 0:
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
                    tmp_retry, tmp_mibs = self.process_snmp_data(
                        varBindTable, metrics, get_mapping
                    )
                    if tmp_mibs:
                        self.load_mibs(tmp_mibs)
                    if tmp_retry:
                        retry = True

        for group_key, metric in metrics.items():
            if "profiles" in metrics[group_key]:
                metrics[group_key]["profiles"] = ",".join(
                    metrics[group_key]["profiles"]
                )
        # logger.debug(f"final metrics {metrics}")
        return retry, metrics

    def load_mibs(self, mibs: List[str]) -> None:
        logger.info(f"loading mib modules {mibs}")
        for mib in mibs:
            if mib:
                self.builder.loadModules(mib)
        # logger.debug("Indexing MIB objects..."),

    def isMIBKnown(self, id: str, oid: str) -> tuple([bool, str]):

        oid_list = tuple(oid.split("."))

        start = 5
        for i in range(len(oid_list), start, -1):
            oid_to_check = ".".join(oid_list[:i])
            if oid_to_check in self.mib_map:
                mib = self.mib_map[oid_to_check]
                logger.debug(f"found {mib} for {id} based on {oid_to_check}")
                return True, mib
        logger.warn(f"no mib found {id} based on {oid}")
        return False, None

    def getVarBinds(self, walk=False, profiles=[]):
        varbinds_bulk = set()
        varbinds_get = set()
        get_mapping = {}
        bulk_mapping = {}
        if walk:
            varbinds_bulk.add(ObjectType(ObjectIdentity("1.3.6")))
        else:
            needed_mibs = []
            required_bulk = {}
            required_get = {}

            # First pass we only look at profiles for a full mib walk
            for profile in profiles:
                # Its possible a profile is removed on upgrade but schedule doesn't yet know
                if profile in self.profiles and "varBinds" in self.profiles[profile]:
                    profile_spec = self.profiles[profile]
                    profile_varbinds = profile_spec["varBinds"]
                    for vb in profile_varbinds:
                        if len(vb) == 1:
                            if vb[0] not in required_bulk:
                                required_bulk[vb[0]] = None
                                bulk_mapping[f"{vb[0]}"] = profile
                        if vb[0] not in needed_mibs:
                            needed_mibs.append(vb[0])

            for profile in profiles:
                # Its possible a profile is removed on upgrade but schedule doesn't yet know
                if profile in self.profiles and "varBinds" in self.profiles[profile]:
                    profile_spec = self.profiles[profile]
                    profile_varbinds = profile_spec["varBinds"]
                    for vb in profile_varbinds:
                        if len(vb) == 2:
                            if (
                                vb[0] not in required_bulk
                                or (required_bulk[vb[0]] and vb[1] not in required_bulk[vb[0]])
                            ):
                                if vb[0] not in required_bulk:
                                    required_bulk[vb[0]] = [vb[1]]
                                    bulk_mapping[f"{vb[0]}:{vb[1]}"] = profile
                                else:
                                    required_bulk[vb[0]].append(vb[1])
                                    bulk_mapping[f"{vb[0]}:{vb[1]}"] = profile

            for mib, entries in required_bulk.items():
                if entries is None:
                    varbinds_bulk.add(ObjectType(ObjectIdentity(mib)))
                else:
                    for entry in entries:
                        varbinds_bulk.add(ObjectType(ObjectIdentity(mib, entry)))

            for profile in profiles:
                # Its possible a profile is removed on upgrade but schedule doesn't yet know
                if profile in self.profiles and "varBinds" in self.profiles[profile]:
                    profile_spec = self.profiles[profile]
                    profile_varbinds = profile_spec["varBinds"]
                    for vb in profile_varbinds:
                        if len(vb) == 3:
                            if vb[0] not in required_bulk:
                                required_get[vb[0]] = {}
                                required_get[vb[0]][vb[1]] = [vb[2]]
                                varbinds_get.add(
                                    ObjectType(ObjectIdentity(vb[0], vb[1], vb[2]))
                                )
                                get_mapping[f"{vb[0]}:{vb[1]}:{vb[2]}"] = profile
                            else:
                                if not required_bulk[vb[0]] or vb[1] not in required_bulk[vb[0]]:
                                    if vb[0] not in required_get:
                                        required_get[vb[0]] = {vb[1]: [vb[2]]}
                                    elif vb[1] not in required_get[vb[0]]:
                                        required_get[vb[0]][vb[1]].append(vb[2])
                                        varbinds_get.add(
                                            ObjectType(
                                                ObjectIdentity(vb[0], vb[1], vb[2])
                                            )
                                        )
                                        get_mapping[
                                            f"{vb[0]}:{vb[1]}:{vb[2]}"
                                        ] = profile
            self.load_mibs(needed_mibs)

        logger.debug(f"varbinds_get={varbinds_get}")
        logger.debug(f"get_mapping={get_mapping}")
        logger.debug(f"varbinds_bulk={varbinds_bulk}")
        logger.debug(f"bulk_mapping={bulk_mapping}")

        return varbinds_get, get_mapping, varbinds_bulk, bulk_mapping

    def process_snmp_data(self, varBindTable, metrics, mapping={}):
        i = 0
        retry = False
        remotemibs = []
        for varBind in varBindTable:
            i += 1
            mib, metric, index = varBind[0].getMibSymbol()

            id = varBind[0].prettyPrint()
            oid = str(varBind[0].getOid())

            # logger.debug(f"{mib}.{metric} id={id} oid={oid} index={index}")

            if isMIBResolved(id):
                group_key = get_group_key(mib, oid, index)
                if group_key not in metrics:
                    metrics[group_key] = {
                        "metrics": {},
                        "fields": {},
                    }
                    if mapping:
                        metrics[group_key]["profiles"] = []

                snmp_val = varBind[1]
                snmp_type = type(snmp_val).__name__

                metric_type = map_metric_type(snmp_type, snmp_val)
                metric_value = valueAsBest(snmp_val.prettyPrint())

                index_number = extract_index_number(index)
                metric_value = fill_empty_value(index_number, metric_value)

                profile = None
                if mapping:
                    profile = mapping.get(
                        f"{mib}:{metric}:{index_number}",
                        mapping.get(f"{mib}:{metric}", mapping.get(mib)),
                    )

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
            else:
                found, mib = self.isMIBKnown(id, oid)
                if not mib in remotemibs:
                    remotemibs.append(mib)
                if found:
                    retry = True
                    break

        return retry, remotemibs
