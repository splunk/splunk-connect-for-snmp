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
import os
import sys

from pysnmp.error import PySnmpError
from pysnmp.hlapi import ContextData
from pysnmp.proto.rfc1902 import OctetString

from splunk_connect_for_snmp.common.inventory_record import InventoryRecord


def getContextData(logger, ir: InventoryRecord) -> ContextData:
    contextEngineId = None
    contextName = ""
    # if ir.version == "3":
    #     location = os.path.join("secrets/snmpv3", ir.secret)
    #     if os.path.exists(location):
    #         contextEngineId = getSecretValue(
    #             location, "contextEngineId", required=False
    #         )
    #         contextName = getSecretValue(
    #             location, "contextName", required=False, default=""
    #         )
    #     logger.debug(
    #         f"======contextEngineId: {contextEngineId}, contextName: {contextName}============="
    #     )
    return ContextData(contextEngineId, contextName)
