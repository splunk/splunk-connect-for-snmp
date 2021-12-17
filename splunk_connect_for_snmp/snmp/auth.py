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
from typing import Union

from pysnmp.error import PySnmpError
from pysnmp.hlapi import (
    CommunityData,
    ContextData,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    getCmd,
)
from pysnmp.proto.api import v2c
from pysnmp.proto.rfc1902 import OctetString
from pysnmp.smi.rfc1902 import ObjectIdentity, ObjectType

from splunk_connect_for_snmp.common.inventory_record import InventoryRecord
from splunk_connect_for_snmp.snmp.const import AuthProtocolMap, PrivProtocolMap
from splunk_connect_for_snmp.snmp.exceptions import SnmpActionError

UDP_CONNECTION_TIMEOUT = int(os.getenv("UDP_CONNECTION_TIMEOUT", 1))


def getSecretValue(
    location: str, key: str, default: str = None, required: bool = False
) -> str:
    source = os.path.join(location, key)
    result = default
    if os.path.exists(source):
        with open(os.path.join(location, key)) as file:
            result = file.read().replace("\n", "")
    elif required:
        raise Exception(f"Required secret key {key} not found in {location}")
    return result


#
# To discover remote SNMP EngineID we will tap on SNMP engine inner workings
# by setting up execution point observer setup on INTERNAL class PDU processing
#
def getSecurityEngineId(logger, ir: InventoryRecord, snmpEngine: SnmpEngine):
    observerContext = {}

    transportTarget = UdpTransportTarget((ir.address, ir.port), timeout=UDP_CONNECTION_TIMEOUT)

    # Register a callback to be invoked at specified execution point of
    # SNMP Engine and passed local variables at execution point's local scope
    snmpEngine.observer.registerObserver(
        lambda e, p, v, c: c.update(securityEngineId=v["securityEngineId"]),
        "rfc3412.prepareDataElements:internal",
        cbCtx=observerContext,
    )

    # Send probe SNMP request with invalid credentials
    authData = UsmUserData("non-existing-user")

    errorIndication, errorStatus, errorIndex, varBinds = next(
        getCmd(
            snmpEngine,
            authData,
            transportTarget,
            ContextData(),
            ObjectType(ObjectIdentity("SNMPv2-MIB", "sysDescr", 0)),
        )
    )

    # See if our SNMP engine received REPORT PDU containing securityEngineId

    if "securityEngineId" not in observerContext:
        raise SnmpActionError(
            f"Can't discover peer EngineID, errorIndication: {errorIndication}"
        )

    securityEngineId = observerContext["securityEngineId"]
    logger.debug(f"securityEngineId={securityEngineId}")
    return securityEngineId


def getAuthV3(logger, ir: InventoryRecord, snmpEngine: SnmpEngine) -> UsmUserData:
    location = os.path.join("secrets/snmpv3", ir.secret)
    if os.path.exists(location):
        userName = getSecretValue(location, "userName", required=True)

        authKey = getSecretValue(location, "authKey", required=False)
        privKey = getSecretValue(location, "privKey", required=False)

        authProtocol = getSecretValue(location, "authProtocol", required=False)
        authProtocol = AuthProtocolMap.get(authProtocol.upper(), "NONE")

        privProtocol = getSecretValue(
            location, "privProtocol", required=False, default="NONE"
        )
        privProtocol = PrivProtocolMap.get(privProtocol.upper(), "NONE")

        authKeyType = int(
            getSecretValue(location, "authKeyType", required=False, default="0")
        )

        privKeyType = int(
            getSecretValue(location, "privKeyType", required=False, default="0")
        )
        if isinstance(ir.securityEngine, str):
            securityEngineId = ir.securityEngine
            logger.debug(f"Security eng from profile {ir.securityEngine}")
        else:
            securityEngineId = getSecurityEngineId(logger, ir, snmpEngine)
            logger.debug(f"Security eng dynamic {securityEngineId}")

        securityName = None
        logger.debug(
            f"{userName},authKey={authKey},privKey={privKey},authProtocol={authProtocol},privProtocol={privProtocol},securityEngineId={securityEngineId},securityName={securityName},authKeyType={authKeyType},privKeyType={privKeyType}"
        )
        return UsmUserData(
            userName,
            authKey=authKey,
            privKey=privKey,
            authProtocol=authProtocol,
            privProtocol=privProtocol,
            securityEngineId=securityEngineId,
            securityName=securityName,
            authKeyType=authKeyType,
            privKeyType=privKeyType,
        )

    else:
        raise Exception(f"invalid username from secret {ir.secret}")


def getAuthV2c(logger, ir: InventoryRecord) -> CommunityData:
    return CommunityData(ir.community, mpModel=1)


def getAuthV1(logger, ir: InventoryRecord) -> CommunityData:
    return CommunityData(ir.community, mpModel=0)


def GetAuth(
    logger, ir: InventoryRecord, snmpEngine: SnmpEngine
) -> Union[UsmUserData, CommunityData]:

    if ir.version == "1":
        return getAuthV1(logger, ir)
    elif ir.version == "2c":
        return getAuthV2c(logger, ir)
    elif ir.version == "3":
        return getAuthV3(logger, ir, snmpEngine)
    else:
        raise ValueError(f"Invalid version unable to generate auth {ir.version}")
