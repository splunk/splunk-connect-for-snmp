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
import pysnmp
import yaml

from splunk_connect_for_snmp.snmp.const import AuthProtocolMap, PrivProtocolMap

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
from celery import Task, shared_task
from celery.utils.log import get_task_logger
from mongolock import MongoLock, MongoLockLocked
from pysnmp.hlapi import *

# from pysnmp.hlapi import (
#     CommunityData,
#     UdpTransportTarget,
#     getCmd,
#     bulkCmd,
#     ContextData,
# )
from pysnmp.proto import rfc1902
from pysnmp.smi import compiler, view
from pysnmp.smi.rfc1902 import ObjectIdentity, ObjectType
from requests_cache import MongoCache

from splunk_connect_for_snmp.common.requests import CachedLimiterSession

logger = get_task_logger(__name__)

MIB_SOURCES = os.getenv("MIB_SOURCES", "https://pysnmp.github.io/mibs/asn1/@mib@")
MIB_INDEX = os.getenv("MIB_INDEX", "https://pysnmp.github.io/mibs/index.csv")
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "sc4snmp")
CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.yaml")


def valueAsBest(value) -> Union[str, float]:
    try:
        return float(value)
    except:
        return value


def _any_failure_happened(
    error_indication, error_status, error_index, var_binds: list
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
        result = f"error: {error_indication}"
        logger.error(result)
    elif error_status:
        result = "error: {} at {}".format(
            error_status.prettyPrint(),
            error_index and var_binds[int(error_index) - 1][0] or "?",
        )
        logger.error(result)
    else:
        return False
    return True


MTYPES_CC = tuple(["Counter32", "Counter64", "TimeTicks"])
MTYPES_C = tuple()
MTYPES_G = tuple(
    ["Gauge32", "Gauge64", "Integer", "Integer32", "Unsigned32", "Unsigned64"]
)
MTYPES_R = tuple(["ObjectIdentifier", "ObjectIdentity"])
MTYPES = tuple(["cc", "c", "g"])


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


class SNMPTask(Task):
    def __init__(self):
        # self.snmpEngine = SnmpEngine()
        self.mongo_client = pymongo.MongoClient(MONGO_URI)

        self.session = CachedLimiterSession(
            per_second=120,
            cache_name="cache_http",
            backend=MongoCache(connection=self.mongo_client, db_name=MONGO_DB),
            expire_after=1800,
            # logger=logger,
            match_headers=False,
            stale_if_error=True,
            allowable_codes=[200],
        )

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
            logger.error(f"Loaded {len(self.mib_map.keys())} mib map entries")
        else:
            logger.error(
                f"Unable to load mib map from index http error {self.mib_response.status_code}"
            )

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

    # @asyncio.coroutine
    def run_walk(self, kwargs):
        varbinds_bulk = []
        get_mibs = []
        bulk_mibs = []
        varbinds_get = []
        metrics = {}
        retry = False

        with open(CONFIG_PATH) as file:
            config_base = yaml.safe_load(file)

        # Connection and Security setup
        target_address = kwargs["address"].split(":")[0]
        target_port = kwargs["address"].split(":")[1]
        auth_data = build_authData(kwargs["version"], kwargs["community"], config_base["poller"])
        context_data = build_contextData(
            kwargs["version"], kwargs["community"], config_base
        )

        transport = UdpTransportTarget((target_address, target_port))

        # What to do
        if kwargs.get("walk", False):
            varbinds_bulk.append(ObjectType(ObjectIdentity("1.3.6")))
        else:
            needed_mibs = []
            for mib, entries in kwargs["varbinds_bulk"].items():
                if entries:
                    for entry in entries:
                        varbinds_bulk.append(ObjectType(ObjectIdentity(mib, entry)))
                    if mib.find(".") == -1 and mib not in needed_mibs:
                        needed_mibs.append(mib)

            for mib, names in kwargs["varbinds_get"].items():
                if names:
                    for name, indexes in names.items():
                        if indexes:
                            for index in indexes:
                                varbinds_get.append(
                                    ObjectType(ObjectIdentity(mib, name, index))
                                )
                if mib.find(".") == -1 and mib not in needed_mibs:
                    needed_mibs.append(mib)
            self.load_mibs(needed_mibs)

        if len(varbinds_bulk) > 0:

            for (errorIndication, errorStatus, errorIndex, varBindTable,) in bulkCmd(
                self.snmpEngine,
                auth_data,
                transport,
                context_data,
                0,
                50,
                *varbinds_bulk,
                lexicographicMode=False,
            ):
                if _any_failure_happened(
                    errorIndication, errorStatus, errorIndex, varBindTable
                ):
                    break
                else:
                    tmp_retry, tmp_mibs = self.process_snmp_data(varBindTable, metrics)
                    if tmp_mibs:
                        bulk_mibs = list(set(bulk_mibs + tmp_mibs))
                    if tmp_retry:
                        retry = True

        if len(varbinds_get) > 0:
            for (errorIndication, errorStatus, errorIndex, varBindTable,) in getCmd(
                self.snmpEngine, auth_data, transport, context_data, *varbinds_get
            ):
                if not _any_failure_happened(
                    errorIndication, errorStatus, errorIndex, varBindTable
                ):
                    tmp_retry, tmp_mibs = self.process_snmp_data(varBindTable, metrics)
                    if tmp_mibs:
                        get_mibs = list(set(bulk_mibs + get_mibs))
                    if tmp_retry:
                        retry = True

        self.load_mibs(bulk_mibs)
        self.load_mibs(get_mibs)
        return retry, metrics

    def process_snmp_data(self, varBindTable, metrics):
        i = 0
        retry = False
        remotemibs = []
        for varBind in varBindTable:
            i += 1
            # logger.debug(varBind)
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

                snmp_val = varBind[1]
                snmp_type = type(snmp_val).__name__

                metric_type = map_metric_type(snmp_type, snmp_val)
                metric_value = valueAsBest(snmp_val.prettyPrint())
                if metric_type in MTYPES and (isinstance(metric_value, float)):
                    metrics[group_key]["metrics"][f"{mib}.{metric}"] = {
                        "type": metric_type,
                        "value": metric_value,
                        "oid": oid,
                    }
                else:
                    if not snmp_val.prettyPrint() == "":
                        metrics[group_key]["fields"][f"{mib}.{metric}"] = {
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


@shared_task(
    bind=True,
    base=SNMPTask,
    expires=21000,
    autoretry_for=[MongoLockLocked],
)
def walk(self, **kwargs):

    retry = True
    mongo_client = pymongo.MongoClient(MONGO_URI)
    lock = MongoLock(client=mongo_client, db="sc4snmp")
    with lock(kwargs["address"], self.request.id, expire=300, timeout=300):
        now = str(time.time())
        while retry:
            retry, result = self.run_walk(kwargs)

    # After a Walk tell schedule to recalc
    work = kwargs
    work["ts"] = now
    work["result"] = result
    work["reschedule"] = True

    return work


@shared_task(
    bind=True,
    base=SNMPTask,
    default_retry_delay=5,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=1,
    retry_jitter=True,
    expires=30,
)
def poll(self, **kwargs):
    mongo_client = pymongo.MongoClient(MONGO_URI)
    lock = MongoLock(client=mongo_client, db="sc4snmp")
    with lock(kwargs["address"], self.request.id, expire=90, timeout=20):
        now = str(time.time())

        # After a Walk tell schedule to recalc
        retry, result = self.run_walk(kwargs)

    # TODO: If profile has third value use get instead
    work = kwargs
    work["ts"] = now
    work["result"] = result
    work["detectchange"] = False

    return work


@shared_task(bind=True, base=SNMPTask)
def trap(self, work):
    now = str(time.time())

    var_bind_table = []
    metrics = {}
    for w in work["data"]:
        translated_var_bind = ObjectType(ObjectIdentity(w[0]), w[1]).resolveWithMib(
            self.mib_view_controller
        )
        var_bind_table.append(translated_var_bind)

    self.process_snmp_data(var_bind_table, metrics)

    return {
        "ts": now,
        "result": metrics,
        "host": work["host"],
        "detectchange": False,
        "sourcetype": "sc4snmp:traps",
    }


def build_authData(version, community, server_config):
    """
    create authData (CommunityData or UsmUserData) instance based on the SNMP's version
    @params version: str, "1" | "2c" | "3"
    @params community:
        for v1/v2c: str, community string/community name, e.g. "public"
        for v3: str, userName
    @params server_config: dict of config.yaml
        for v3 to lookup authKey/privKey using userName
    @return authData class instance
        for v1/v2c: CommunityData class instance
        for v3: UsmUserData class instance
    reference: https://github.com/etingof/pysnmp/blob/master/pysnmp/hlapi/v3arch/auth.py
    """
    if version == "3":
        try:
            # Essential params for SNMP v3
            # UsmUserData(userName, authKey=None, privKey=None)
            userName = community
            authKey = None
            privKey = None
            authProtocol = None
            privProtocol = None
            securityEngineId = None
            securityName = None
            authKeyType = 0
            privKeyType = 0

            if server_config["usernames"].get(userName, None):
                authKey = server_config["usernames"][userName].get("authKey", None)
                privKey = server_config["usernames"][userName].get("privKey", None)

                authProtocol = server_config["usernames"][userName].get(
                    "authProtocol", None
                )
                if authProtocol:
                    authProtocol = AuthProtocolMap.get(authProtocol.upper(), "NONE")
                privProtocol = server_config["usernames"][userName].get(
                    "privProtocol", None
                )
                if privProtocol:
                    privProtocol = PrivProtocolMap.get(privProtocol.upper(), "NONE")
                securityEngineId = server_config["usernames"][userName].get(
                    "securityEngineId", None
                )
                if securityEngineId:
                    securityEngineId = pysnmp.proto.rfc1902.OctetString(
                        hexValue=str(securityEngineId)
                    )
                securityName = server_config["usernames"][userName].get(
                    "securityName", None
                )
                authKeyType = int(
                    server_config["usernames"][userName].get("authKeyType", 0)
                )  # USM_KEY_TYPE_PASSPHRASE
                privKeyType = int(
                    server_config["usernames"][userName].get("privKeyType", 0)
                )  # USM_KEY_TYPE_PASSPHRASE
        except Exception as e:
            logger.error(
                f"Error happend while parsing parmas of UsmUserData for SNMP v3: {e}"
            )
        try:
            logger.debug(
                f"=============\nuserName - {userName}, authKey - {authKey}, privKey - {privKey}"
            )
            return UsmUserData(
                userName,
                authKey,
                privKey,
                authProtocol,
                privProtocol,
                securityEngineId,
                securityName,
                authKeyType,
                privKeyType,
            )
        except Exception as e:
            logger.error(f"Error happend while building UsmUserData for SNMP v3: {e}")
    else:
        try:
            # Essential params for SNMP v1/v2c
            # CommunityData(community_string, mpModel)
            communityName = community
            communityIndex = None
            contextEngineId = None
            contextName = None
            tag = None
            securityName = None
            if server_config["communities"].get(communityName, None):
                communityIndex = server_config["communities"][communityName].get(
                    "communityIndex", None
                )
                contextEngineId = server_config["communities"][communityName].get(
                    "contextEngineId", None
                )
                contextName = server_config["communities"][communityName].get(
                    "contextName", None
                )
                tag = server_config["communities"][communityName].get("tag", None)
                securityName = server_config["communities"][communityName].get(
                    "securityName", None
                )
            logger.debug(
                f"\ncommunityName - {communityName}, "
                f"communityIndex - {communityIndex}, "
                f"contextEngineId - {contextEngineId}, "
                f"contextName - {contextName}, "
                f"tag - {tag}, "
                f"securityName - {securityName}"
            )
        except Exception as e:
            logger.exception(
                f"Error happend while parsing parmas of communityName for SNMP v1/v2c: {e}"
            )
        if version == "1":
            # for SNMP v1
            # CommunityData(community_string, mpModel=0)
            try:
                # return CommunityData(community, mpModel=0)
                mpModel = 0
                return CommunityData(
                    communityIndex,
                    communityName,
                    mpModel,
                    contextEngineId,
                    contextName,
                    tag,
                    securityName,
                )
            except Exception as e:
                logger.error(
                    f"Error happend while building CommunityData for SNMP v1: {e}"
                )
        else:
            # for SNMP v2c
            # CommunityData(community_string, mpModel=1)
            try:
                # return CommunityData(community, mpModel=1)
                mpModel = 1
                return CommunityData(
                    communityIndex,
                    communityName,
                    mpModel,
                    contextEngineId,
                    contextName,
                    tag,
                    securityName,
                )
            except Exception as e:
                logger.error(
                    f"Error happend while building CommunityData for SNMP v2c: {e}"
                )


def build_contextData(version, community, server_config):
    """
    create ContextData instance based on the SNMP's version
    for SNMP v1/v2c, use the default ContextData with contextName as empty string
    for SNMP v3, users can specify contextName, o.w. use empty string as contextName
    @params version: str, "1" | "2c" | "3"
    @params community:
        for v1/v2c: str, community string/community name, e.g. "public"
        for v3: str, userName
    @params server_config: dict of config.yaml
        for v3 to lookup authKey/privKey using userName
    @return ContextData class instance
        for v1/v2c: default ContextData(contextEngineId=None, contextName='')
        for v3: can specify contextName ContextData(contextEngineId=None, contextName=<contextName>)
    reference: https://pysnmp.readthedocs.io/en/latest/docs/api-reference.html
    """
    contextEngineId = None
    contextName = ""
    try:
        if version == "3" and server_config["usernames"].get(community, None):
            contextEngineId = server_config["usernames"][community].get(
                "contextEngineId", None
            )
            contextName = server_config["usernames"][community].get("contextName", "")
        logger.debug(
            f"======contextEngineId: {contextEngineId}, contextName: {contextName}============="
        )
    except Exception as e:
        logger.error(f"Error happend while parsing params for ContextData: {e}")
    try:
        return ContextData(contextEngineId, contextName)
    except Exception as e:
        logger.error(f"Error happend while building ContextData: {e}")
