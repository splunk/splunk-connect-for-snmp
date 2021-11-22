try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass

import os
import time
from collections import namedtuple
from typing import List

import pymongo
import yaml
from bson.objectid import ObjectId
from celery import Task, shared_task
from celery.utils.log import get_task_logger
from pysnmp.hlapi import *
from pysnmp.smi import builder, compiler, view
from requests_cache import MongoCache

from splunk_connect_for_snmp.common.requests import CachedLimiterSession
from splunk_connect_for_snmp.poller import app

logger = get_task_logger(__name__)

MIB_SOURCES = os.getenv("MIB_SOURCES", "https://pysnmp.github.io/mibs/asn1/@mib@")
MIB_INDEX = os.getenv("MIB_INDEX", "https://pysnmp.github.io/mibs/index/")
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "sc4snmp")


class VarbindCollection(namedtuple("VarbindCollection", "get, bulk")):
    def __add__(self, other):
        return VarbindCollection(bulk=self.bulk + other.bulk, get=self.get + other.get)


def translate_list_to_oid(varbind):
    return ObjectType(ObjectIdentity(*varbind)).addAsn1MibSource(MIB_SOURCES).loadMibs()


def mib_string_handler(mib_list: list) -> VarbindCollection:
    """
    Perform the SNMP Get for mib-name/string, where mib string is a list
    1) case 1: with mib index - consider it as a single oid -> snmpget
    e.g. ['SNMPv2-MIB', 'sysUpTime',0] (syntax -> [<mib_file_name>, <mib_name/string>, <min_index>])

    2) case 2: without mib index - consider it as a oid with * -> snmpbulkwalk
    . ['SNMPv2-MIB', 'sysORUpTime'] (syntax -> [<mib_file_name>, <mib_name/string>)
    """
    if not mib_list:
        return VarbindCollection(get=[], bulk=[])
    get_list, bulk_list = [], []
    for mib_string in mib_list:
        try:
            if not isinstance(mib_string, list):
                bulk_list.append(ObjectType(ObjectIdentity(mib_string)))
                continue
            oid = translate_list_to_oid(mib_string)
            mib_string_length = len(mib_string)
            if mib_string_length == 3:
                get_list.append(oid)
            elif mib_string_length < 3:
                bulk_list.append(oid)
            else:
                raise Exception(
                    f"Invalid mib string - {mib_string}."
                    f"\nPlease provide a valid mib string in the correct format. "
                    f"Learn more about the format at https://bit.ly/3qtqzQc"
                )
        except Exception as e:
            logger.error(f"Error happened translating string: {mib_string}: {e}")
    return VarbindCollection(get=get_list, bulk=bulk_list)


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


def load_mibs(mibs: List[str]) -> None:
    mibBuilder = builder.MibBuilder()
    logger.info("This worker requires additional mibs")
    # Optionally attach PySMI MIB compiler (if installed)
    logger.debug("Attaching MIB compiler...")
    compiler.addMibCompiler(mibBuilder, sources=[MIB_SOURCES])
    logger.debug("Loading MIB modules..."),
    logger.info(f"loading mib modules {','.join(mibs)}")
    for mib in mibs:
        mibBuilder.loadModules(mib)
    logger.debug("Indexing MIB objects..."),


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
            allowable_codes=[200, 404],
        )
        load_mibs(
            [
                "HOST-RESOURCES-MIB",
                "IANAifType-MIB",
                "IF-MIB",
                "IP-MIB",
                "RFC1389-MIB",
                "SNMPv2-MIB",
                "UCD-SNMP-MIB",
                "TCP-MIB",
                "UDP-MIB",
            ]
        )
        self.snmpEngine = SnmpEngine()
        # self.index: dict = {}

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
        start = 3
        if start + 4 > len(oid_list):
            end = len(oid_list)
        else:
            end = start + 3
        if start > end:
            return False, []
        for i in range(end, start, -1):
            oid_to_check = "/".join(oid_list[:i])

            response = self.session.request(
                "GET", f"{MIB_INDEX}{oid_to_check}/mib.txt", timeout=90
            )
            if response.status_code == 200:
                logger.debug(f"found for {id} based on {oid_to_check}")
                logger.debug(response.content)
                mibs = response.content.decode("utf-8").splitlines()
                if "" in mibs:
                    mibs.remove("")
                return found, mibs
        # logger.error(f"No MIB found for {id}")
        return found, mibs

    def return_snmp_iterators(
        self, varbind_collection, communitydata, udp_transport_target
    ):
        bulk_varbinds, get_varbinds = varbind_collection.bulk, varbind_collection.get
        bulk_iterator, get_iterator = None, None
        if bulk_varbinds:
            bulk_iterator = bulkCmd(
                self.snmpEngine,
                communitydata,
                udp_transport_target,
                ContextData(),
                0,
                50,
                *bulk_varbinds,
                lexicographicMode=False,
            )
        if get_varbinds:
            get_iterator = getCmd(
                self.snmpEngine,
                communitydata,
                udp_transport_target,
                ContextData(),
                *get_varbinds,
            )
        return bulk_iterator, get_iterator

    # @asyncio.coroutine
    def run_walk(self, id: str, profiles: List[str] = None, walk: bool = False):

        mongo_client = pymongo.MongoClient(MONGO_URI)
        targets_collection = mongo_client.sc4snmp.targets
        target = targets_collection.find_one(
            {"_id": ObjectId(id)}, {"target": True, "config": {"community": True}}
        )

        if walk:
            var_binds = ["1.3.6"]
        else:
            with open("config.yaml") as file:
                config_base = yaml.safe_load(file)
            var_binds = []

            for profile in profiles:
                # TODO: Add profile name back to metric
                if profile in config_base["poller"]["profiles"]:
                    profile_varbinds = config_base["poller"]["profiles"][profile][
                        "varBinds"
                    ]
                    var_binds += profile_varbinds

        varbind_collection = mib_string_handler(var_binds)
        logger.debug(
            f"{len(varbind_collection.bulk)} events for bulk, {len(varbind_collection.get)} events for get"
        )
        logger.debug(f"target = {target}")

        metrics = {}
        retry = False
        seedmibs = []
        logger.debug(f"Walking {target} for {varbind_collection}")

        target_address = target["target"].split(":")[0]
        target_port = target["target"].split(":")[1]
        if target["config"]["community"]["version"] in ("1", "2", "2c"):
            communitydata = CommunityData(target["config"]["community"]["name"])
        else:
            raise NotImplementedError("version 3 not yet implemented")
        bulk_iterator, get_iterator = self.return_snmp_iterators(
            varbind_collection,
            communitydata,
            UdpTransportTarget((target_address, target_port)),
        )
        if bulk_iterator:
            for (
                errorIndication,
                errorStatus,
                errorIndex,
                varBindTable,
            ) in bulk_iterator:
                if _any_failure_happened(
                    errorIndication, errorStatus, errorIndex, varBindTable
                ):
                    break
                else:
                    retry = self.process_snmp_data(varBindTable, metrics, seedmibs)

        if get_iterator:
            for (
                errorIndication,
                errorStatus,
                errorIndex,
                varBindTable,
            ) in get_iterator:
                if not _any_failure_happened(
                    errorIndication, errorStatus, errorIndex, varBindTable
                ):
                    retry = self.process_snmp_data(varBindTable, metrics, seedmibs)

        # self.snmpEngine.transportDispatcher.closeDispatcher()
        if len(seedmibs) > 0:
            load_mibs(seedmibs)
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
                if not group_key in metrics:
                    metrics[group_key] = {
                        "metrics": {},
                        "fields": {},
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
        retry, result = self.run_walk(
            kwargs["id"],
            walk=True,
        )
    # TODO if needed send talk

    # After a Walk tell schedule to recalc
    work = {"id": kwargs["id"], "ts": now, "result": result, "reschedule": True}

    return work


@shared_task(bind=True, base=SNMPTask)
def poll(self, **kwargs):
    retry = True
    now = str(time.time())

    # After a Walk tell schedule to recalc
    retry, result = self.run_walk(
        kwargs["id"],
        profiles=kwargs["profiles"],
    )

    # TODO: If profile has third value use get instead

    work = {"id": kwargs["id"], "ts": now, "result": result, "detectchange": False}

    return work


@shared_task(bind=True, base=SNMPTask)
def trap(self, work):
    now = str(time.time())

    # work = {"id": transportAddress, "data": data}

    for w in work["data"]:
        logger.debug(f"Trap received {w[0]} = {w[1]}")
        ObjectType(ObjectIdentity(w[0]))

    # app.send_task(
    #     "splunk_connect_for_snmp.enrich.tasks.enrich",
    #     kwargs=(
    #         {"id": kwargs["id"], "ts": now, "result": result, "detectchange": True}
    #     ),
    # )

    return {}
