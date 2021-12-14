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

import yaml
from pysnmp.smi.error import SmiError

from splunk_connect_for_snmp.snmp.exceptions import SnmpActionError

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
from pysnmp.smi.rfc1902 import ObjectIdentity, ObjectType

from splunk_connect_for_snmp.common.inventory_record import (
    InventoryRecord,
    InventoryRecordEncoder,
)
from splunk_connect_for_snmp.common.requests import CachedLimiterSession
from splunk_connect_for_snmp.snmp.manager import Poller

logger = get_task_logger(__name__)

MIB_SOURCES = os.getenv("MIB_SOURCES", "https://pysnmp.github.io/mibs/asn1/@mib@")
MIB_INDEX = os.getenv("MIB_INDEX", "https://pysnmp.github.io/mibs/index.csv")
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "sc4snmp")
CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.yaml")


@shared_task(
    bind=True,
    base=Poller,
    retry_backoff=30,
    retry_jitter=True,
    retry_backoff_max=3600,
    max_retries=50,
    autoretry_for=(MongoLockLocked, SnmpActionError,),
    throws=(SnmpActionError, SnmpActionError,)
)
def walk(self, **kwargs):
    address = kwargs["address"]
    mongo_client = pymongo.MongoClient(MONGO_URI)

    lock = MongoLock(client=mongo_client, db="sc4snmp")

    with lock(address, self.request.id, expire=300, timeout=300):
        # retry = True
        # while retry:
        retry, result = self.dowork(address, walk=True)
        # retry, result = self.run_walk(kwargs)

    # After a Walk tell schedule to recalc
    work = {}
    work["time"] = time.time()
    work["address"] = address
    work["result"] = result
    # work["reschedule"] = True

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
    mongo_client = pymongo.MongoClient(MONGO_URI)
    lock = MongoLock(client=mongo_client, db="sc4snmp")
    with lock(kwargs["address"], self.request.id, expire=90, timeout=20):
        # retry = True
        # while retry:
        retry, result = self.dowork(address, profiles=profiles)
        # retry, result = self.run_walk(kwargs)

    # After a Walk tell schedule to recalc
    work = {}
    work["time"] = time.time()
    work["address"] = address
    work["result"] = result
    work["detectchange"] = False
    work["frequency"] = kwargs["frequency"]

    return work


@shared_task(bind=True, base=Poller)
def trap(self, work):
    var_bind_table = []
    not_translated_oids = []
    remaining_oids = []
    remotemibs = set()
    metrics = {}
    for w in work["data"]:
        try:
            var_bind_table.append(ObjectType(ObjectIdentity(w[0]), w[1]).resolveWithMib(self.mib_view_controller))
        except SmiError:
            not_translated_oids.append((w[0], w[1]))

    for oid in not_translated_oids:
        found, mib = self.isMIBKnown(oid[0], oid[0])
        if found:
            remotemibs.add(mib)
            remaining_oids.append((oid[0], oid[1]))

    if remotemibs:
        self.load_mibs(remotemibs)
        for w in remaining_oids:
            try:
                var_bind_table.append(ObjectType(ObjectIdentity(w[0]), w[1]).resolveWithMib(self.mib_view_controller))
            except SmiError:
                logger.warn(f"No translation found for {w[0]}")

    self.process_snmp_data(var_bind_table, metrics)

    return {
        "time": time.time(),
        "result": metrics,
        "address": work["host"],
        "detectchange": False,
        "sourcetype": "sc4snmp:traps",
    }
