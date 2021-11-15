try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass

import asyncio
import json
import os
import sys
import traceback
from collections import OrderedDict, namedtuple
from datetime import datetime
from typing import List

import pymongo
from bson.objectid import ObjectId
from celery import Task, shared_task
from celery.utils.log import get_task_logger

# from pysnmp.hlapi import ObjectIdentity, ObjectType, SnmpEngine
# from pysnmp.hlapi.asyncio import *
from pysnmp.hlapi import *
from pysnmp.smi import builder, compiler, error, view
from requests_cache import MongoCache
import yaml

from splunk_connect_for_snmp.app import app
from splunk_connect_for_snmp.common.requests import CachedLimiterSession

logger = get_task_logger(__name__)

MIB_SOURCES = os.getenv("MIB_SOURCES").split(";")
MIB_INDEX = os.getenv("MIB_INDEX")
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "sc4")


def load_mibs(mibs) -> None:
    mibBuilder = builder.MibBuilder()
    logger.info("This worker requires additional mibs")
    # Optionally attach PySMI MIB compiler (if installed)
    logger.debug("Attaching MIB compiler...")
    compiler.addMibCompiler(mibBuilder, sources=MIB_SOURCES)
    logger.debug("Loading MIB modules..."),
    logger.info(f"loading mib modules {','.join(mibs)}")
    for mib in mibs:
        mibBuilder.loadModules(mib)
    logger.debug("Indexing MIB objects..."),
    mibView = view.MibViewController(mibBuilder)


MTYPES_CC = tuple(["Counter32", "Counter64", "TimeTicks"])
MTYPES_C = tuple()
MTYPES_G = tuple(
    ["Gauge32", "Gauge64", "Integer", "Integer32", "Unsigned32", "Unsigned64"]
)
MTYPES_R = tuple(["ObjectIdentifier", "ObjectIdentity"])
MTYPES = tuple(["cc", "c", "g"])


def isMIBResolved(id):
    if id.startswith("RFC1213-MIB::mib-") or id.startswith("SNMPv2-SMI::enterprises."):
        return False
    else:
        return True


def get_group_key(mib, oid, index):
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
            f = float(snmp_value)
        except:
            logger.warn("Logic says this is a metric but the data says its not")
            metric_type = "te"
    return metric_type


def isMIBKnown(id: str, oid: str) -> tuple([bool, List]):
    session = CachedLimiterSession(
        per_second=120,
        cache_name="cache_http",
        backend=MongoCache(url=MONGO_URI, db=MONGO_DB),
        expire_after=300,
        logger=logger,
        match_headers=False,
        stale_if_error=True,
    )
    index: dict = {}
    mibs = []
    found = False
    response = session.request("GET", MIB_INDEX, timeout=90)
    if response.status_code == 200:
        logger.debug(response)
        index = json.loads(response.content)
    oid_list = tuple(oid.split("."))

    if id.startswith("RFC1213-MIB::mib-"):
        start = 4
    elif id.startswith("SNMPv2-SMI::enterprises."):
        start = 8
    else:
        start = 8

    for i in range(len(oid_list), start, -1):
        oid_to_check = ".".join(oid_list[:i])
        logger.debug(f"Checking for {id} based on {oid_to_check}")
        if oid_to_check in index["identity"]:
            mibs = list(set(mibs + index["identity"][oid_to_check]))
            found = True
            break
    logger.debug(f"MIB Finder {id} found={found} mibs={mibs}")
    return found, mibs


# @asyncio.coroutine
def run_walk(id: str, profiles: List[str] = None, walk: bool = False):

    mongo_client = pymongo.MongoClient(MONGO_URI)
    targets_collection = mongo_client.sc4.targets
    target = targets_collection.find_one(
        {"_id": ObjectId(id)}, {"target": True, "config": {"community": True}}
    )

    if walk:
        varBinds = [
            ObjectType(
                ObjectIdentity("1.3.6").addAsn1MibSource(
                    "file:///Users/rfaircloth/splunk/github/GitHub/splunk-connect-for-snmp-mib-server/mibs/asn1",
                )
            ).loadMibs()
        ]
    else:
        varBinds: list[ObjectType] = []
        with open("config.yaml", "r") as file:
            config_base = yaml.safe_load(file)

        var_binds = []

        for profile in profiles:
            if profile in config_base["poller"]["profiles"]:
                for varBind in config_base["poller"]["profiles"][profile]["varBinds"]:
                    logger.debug(f"varBind {varBind}")
                    if len(varBind) == 3:
                        varBinds.append(
                            ObjectType(
                                ObjectIdentity(
                                    varBind[0], varBind[1], varBind[2]
                                ).addAsn1MibSource(
                                    "file:///Users/rfaircloth/splunk/github/GitHub/splunk-connect-for-snmp-mib-server/mibs/asn1/@mib@",
                                )
                            ).loadMibs()
                        )
                    elif len(varBind) == 2:
                        varBinds.append(
                            ObjectType(
                                ObjectIdentity(varBind[0], varBind[1]).addAsn1MibSource(
                                    "file:///Users/rfaircloth/splunk/github/GitHub/splunk-connect-for-snmp-mib-server/mibs/asn1/@mib@",
                                )
                            ).loadMibs()
                        )
                    else:
                        continue
        #         var_binds = (
        #             var_binds
        #             + config_base["poller"]["profiles"][profile]["varBinds"]
        #         )

        # logger.debug(f"Active raw Varbinds {var_binds}")
        # varBindsCollection = sort_varbinds(var_binds)
        # sorted_varBinds = varBindsCollection.bulk
        # logger.debug(f"Varbind collection: {sorted_varBinds}")

        # for varBind in config_base['poller']["profiles"][profile]["varBinds"]:
        #     varBinds.append(
        #         ObjectType(
        #             ObjectIdentity(varBind).addAsn1MibSource(
        #                 "file:///Users/rfaircloth/splunk/github/GitHub/splunk-connect-for-snmp-mib-server/mibs/asn1",
        #             )
        #         ).loadMibs()
        #     )

    logger.debug(target)
    i = 0
    metrics = OrderedDict()
    retry = False
    seedmibs = []
    logger.debug(f"Walking {target} for {varBinds}")

    target_address = target["target"].split(":")[0]
    target_port = target["target"].split(":")[1]
    if target["config"]["community"]["version"] in ("1", "2", "2c"):
        communitydata = CommunityData(target["config"]["community"]["name"])
    else:
        raise NotImplementedError("version 3 not yet implemented")

    snmpEngine = SnmpEngine()
    # while True:
    iterator = bulkCmd(
        snmpEngine,
        communitydata,
        UdpTransportTarget((target_address, target_port)),
        ContextData(),
        0,
        50,
        *varBinds,
    )
    for errorIndication, errorStatus, errorIndex, varBindTable in iterator:

        # errorIndication, errorStatus, errorIndex, varBindTable = yield from iterator

        if errorIndication:
            logger.error(errorIndication)
            # snmpEngine.transportDispatcher.closeDispatcher()
            # raise Exception(errorIndication)
            break
        elif errorStatus:
            logger.error(
                "%s at %s"
                % (
                    errorStatus.prettyPrint(),
                    errorIndex and varBinds[int(errorIndex) - 1][0] or "?",
                )
            )
            break
 
        else:
            # for varBindRow in varBindTable:
            for varBind in varBindTable:
                i += 1
                logger.debug(varBind)
                mib, metric, index = varBind[0].getMibSymbol()

                id = varBind[0].prettyPrint()
                oid = str(varBind[0].getOid())

                logger.debug(f"{mib}.{metric} id={id} oid={oid}")

                if isMIBResolved(id):
                    group_key = get_group_key(mib, oid, index)
                    if not group_key in metrics:
                        metrics[group_key] = {
                            "metrics": OrderedDict(),
                            "fields": OrderedDict(),
                        }

                    snmp_val = varBind[1]
                    snmp_type = type(snmp_val).__name__

                    metric_type = map_metric_type(snmp_type, snmp_val)
                    if metric_type in MTYPES:
                        metrics[group_key]["metrics"][f"{mib}.{metric}"] = {
                            "type": metric_type,
                            "value": snmp_val.prettyPrint(),
                            "oid": oid,
                        }
                    else:
                        if not snmp_val.prettyPrint() == "":
                            metrics[group_key]["fields"][f"{mib}.{metric}"] = {
                                "type": metric_type,
                                "value": snmp_val.prettyPrint(),
                                "oid": oid,
                            }

                else:
                    found, remotemibs = isMIBKnown(id, oid)
                    if found:
                        retry = True
                        seedmibs = list(set(remotemibs + seedmibs))

        # varBinds = varBindTable[-1]
        # if isEndOfMib(varBinds):
        #     logger.debug("Completed Walk")
        #     break

    snmpEngine.transportDispatcher.closeDispatcher()
    if len(seedmibs) > 0:
        load_mibs(seedmibs)
    return retry, metrics


class SNMPTask(Task):
    def __init__(self):
        # self.snmpEngine = SnmpEngine()

        # self.session = CachedLimiterSession(
        #     per_second=120,
        #     cache_name="cache_http",
        #     backend=MongoCache(url=MONGO_URI, db=MONGO_DB),
        #     expire_after=300,
        #     logger=logger,
        #     match_headers=False,
        #     stale_if_error=True,
        # )
        # self.index: dict = {}
        pass


@shared_task(bind=True, base=SNMPTask)
# This task gets the inventory and creates a task to schedules each walk task
def walk(self, **kwargs):

    retry = True
    now = datetime.utcnow().timestamp()
    # loop = asyncio.get_event_loop()
    # while retry:
    #     retry, result = loop.run_until_complete(
    #         run_walk(
    #             kwargs["id"],
    #             walk=True,
    #         )
    #     )
    # loop.close()
    while retry:
        #     retry, result  = asyncio.run(run_walk(
        #             kwargs["id"],
        #             walk=True,
        #         ))
        retry, result = run_walk(
            kwargs["id"],
            walk=True,
        )
    ##TODO if needed send talk

    # After a Walk tell schedule to recalc
    app.send_task(
        "splunk_connect_for_snmp.enrich.tasks.enrich",
        kwargs=({"id": kwargs["id"], "ts": now, "result": result, "reschedule": True}),
    )
    return result


@shared_task(bind=True, base=SNMPTask)
# This task gets the inventory and creates a task to schedules each walk task
def poll(self, **kwargs):
    retry = True
    now = datetime.utcnow().timestamp()
    # retry, result = asyncio.run(run_walk(
    #         kwargs["id"],
    #         profiles=kwargs["profiles"],
    #     ))
    # loop = asyncio.get_event_loop()

    # retry, result = loop.run_until_complete(
    #     run_walk(
    #         kwargs["id"],
    #         profiles=kwargs["profiles"],
    #     )
    # )
    # loop.close()

    ##TODO if needed send talk

    # After a Walk tell schedule to recalc
    retry, result = run_walk(
        kwargs["id"],
        profiles=kwargs["profiles"],
    )

    app.send_task(
        "splunk_connect_for_snmp.enrich.tasks.enrich",
        kwargs=(
            {"id": kwargs["id"], "ts": now, "result": result, "detectchange": True}
        ),
    )

    return result
