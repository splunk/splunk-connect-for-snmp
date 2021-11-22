try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass

import os
import time
from collections import namedtuple
from io import StringIO
from typing import List, Union

import pymongo
import yaml
from bson.objectid import ObjectId
from celery import Task, shared_task
from celery.utils.log import get_task_logger
from pysnmp.hlapi import *

# from pysnmp.hlapi import (
#     CommunityData,
#     UdpTransportTarget,
#     getCmd,
#     bulkCmd,
#     ContextData,
# )
from pysnmp.smi import builder, compiler, view
from requests_cache import MongoCache

from splunk_connect_for_snmp.common.requests import CachedLimiterSession
from splunk_connect_for_snmp.poller import app

logger = get_task_logger(__name__)

MIB_SOURCES = os.getenv("MIB_SOURCES", "https://pysnmp.github.io/mibs/asn1/@mib@")
MIB_INDEX = os.getenv("MIB_INDEX", "https://pysnmp.github.io/mibs/index.csv")
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "sc4snmp")


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
    if id.startswith("RFC1213-MIB::") or id.startswith("SNMPv2-SMI::enterprises."):
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
            with StringIO(mib_response.text) as response_content:
                for line in response_content:
                    entry = line.split(",")
                    if not len(entry) == 2:
                        self.mib_map[entry[1]] = entry[0]
            logger.debug(f"Loaded {len(self.mib_map.keys())} mib map entries")
        else:
            logger.error(
                f"Unable to load mib map from index http error {self.mib_response.status_code}"
            )

    def load_mibs(self, mibs: List[str]) -> None:
        logger.info(f"loading mib modules {','.join(mibs)}")
        for mib in mibs:
            self.builder.loadModules(mib)
        # logger.debug("Indexing MIB objects..."),

    def isMIBKnown(self, id: str, oid: str) -> tuple([bool, List]):

        mibs = []
        found = False
        oid_list = tuple(oid.split("."))

        # if id.startswith("RFC1213-MIB::mib-"):
        #     start = 6
        # elif id.startswith("SNMPv2-SMI::enterprises."):
        #     start = 8
        # else:
        #     start = 8
        start = 5
        if start + 4 > len(oid_list):
            end = len(oid_list)
        else:
            end = start + 3
        if start > end:
            return False, []
        for i in range(end, start, -1):
            oid_to_check = ".".join(oid_list[:i])
            if oid_to_check in self.mib_map:
                mibs = [mib_map[oid_to_check]]
                logger.debug(f"found {mibs} for {id} based on {oid_to_check}")
                return found, mibs
        return found, mibs

    # @asyncio.coroutine
    def run_walk(self, kwargs):
        varbinds_bulk = []
        varbinds_get = []
        metrics = {}
        retry = False
        seedmibs = []

        # Connection and Security setup
        target_address = kwargs["address"].split(":")[0]
        target_port = kwargs["address"].split(":")[1]
        if kwargs["version"] in ("1", "2", "2c"):
            communitydata = CommunityData(kwargs["community"])
        else:
            raise NotImplementedError("version 3 not yet implemented")
        transport = UdpTransportTarget((target_address, target_port))

        # What to do
        if kwargs.get("walk", False):
            varbinds_bulk.append(ObjectType(ObjectIdentity("1.3.6")))
        else:
            for mib, entries in kwargs["varbinds_bulk"].items():
                for entry in entries:
                    varbinds_bulk.append(ObjectType(ObjectIdentity(mib, entry)))

        if len(varbinds_bulk) > 0:

            for (errorIndication, errorStatus, errorIndex, varBindTable,) in bulkCmd(
                self.snmpEngine,
                communitydata,
                transport,
                ContextData(),
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
                    retry = self.process_snmp_data(varBindTable, metrics, seedmibs)

        if len(varbinds_get) > 0:
            for (errorIndication, errorStatus, errorIndex, varBindTable,) in getCmd(
                self.snmpEngine, communitydata, transport, ContextData(), *varbinds_get
            ):
                if not _any_failure_happened(
                    errorIndication, errorStatus, errorIndex, varBindTable
                ):
                    retry = self.process_snmp_data(varBindTable, metrics, seedmibs)

        if len(seedmibs) > 0:
            self.load_mibs(seedmibs)
        return retry, metrics

    def process_snmp_data(self, varBindTable, metrics, seedmibs):
        i = 0
        retry = False
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
                found, remotemibs = self.isMIBKnown(id, oid)
                if found:
                    retry = True
                    seedmibs = list(set(remotemibs + seedmibs))
                    break

        return retry


@shared_task(bind=True, base=SNMPTask)
def walk(self, **kwargs):

    retry = True
    now = str(time.time())
    while retry:
        retry, result = self.run_walk(kwargs)
    # TODO if needed send talk

    # After a Walk tell schedule to recalc
    work = {"id": kwargs["id"], "ts": now, "result": result, "reschedule": True}

    return work


@shared_task(bind=True, base=SNMPTask)
def poll(self, **kwargs):
    retry = True
    now = str(time.time())

    # After a Walk tell schedule to recalc
    retry, result = self.run_walk(kwargs)

    # TODO: If profile has third value use get instead

    work = {"id": kwargs["id"], "ts": now, "result": result, "detectchange": False}

    return work
