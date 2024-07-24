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
from typing import Any, Dict, Union

from pysnmp.hlapi import (
    CommunityData,
    ContextData,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    getCmd,
)
from pysnmp.proto.api.v2c import OctetString
from pysnmp.smi.rfc1902 import ObjectIdentity, ObjectType

from splunk_connect_for_snmp.common.inventory_record import InventoryRecord
from splunk_connect_for_snmp.snmp.const import AuthProtocolMap, PrivProtocolMap
from splunk_connect_for_snmp.snmp.exceptions import SnmpActionError

UDP_CONNECTION_TIMEOUT = int(os.getenv("UDP_CONNECTION_TIMEOUT", 1))


def get_secret_value(
    location: str, key: str, default: str = "", required: bool = False
) -> str:
    source = os.path.join(location, key)
    result = default
    if os.path.exists(source):
        with open(os.path.join(location, key), encoding="utf-8") as file:
            result = file.read().replace("\n", "")
    elif required:
        raise FileNotFoundError(f"Required secret key {key} not found in {location}")
    return result


#
# To discover remote SNMP EngineID we will tap on SNMP engine inner workings
# by setting up execution point observer setup on INTERNAL class PDU processing
#
def get_security_engine_id(logger, ir: InventoryRecord, snmp_engine: SnmpEngine):
    observer_context: Dict[Any, Any] = {}

    transport_target = UdpTransportTarget(
        (ir.address, ir.port), timeout=UDP_CONNECTION_TIMEOUT
    )

    # Register a callback to be invoked at specified execution point of
    # SNMP Engine and passed local variables at execution point's local scope
    snmp_engine.observer.registerObserver(
        lambda e, p, v, c: c.update(securityEngineId=v["securityEngineId"]),
        "rfc3412.prepareDataElements:internal",
        cbCtx=observer_context,
    )

    # Send probe SNMP request with invalid credentials
    auth_data = UsmUserData("non-existing-user")

    error_indication, _, _, _ = next(
        getCmd(
            snmp_engine,
            auth_data,
            transport_target,
            ContextData(),
            ObjectType(ObjectIdentity("SNMPv2-MIB", "sysDescr", 0)),
        )
    )

    # See if our SNMP engine received REPORT PDU containing securityEngineId
    security_engine_id = fetch_security_engine_id(
        observer_context, error_indication, ir.address
    )
    logger.debug(f"securityEngineId={security_engine_id} for device {ir.address}")
    return security_engine_id


def fetch_security_engine_id(observer_context, error_indication, ipaddress):
    if "securityEngineId" in observer_context:
        return observer_context["securityEngineId"]
    else:
        raise SnmpActionError(
            f"Can't discover peer EngineID for device {ipaddress}, errorIndication: {error_indication}"
        )


def get_auth_v3(logger, ir: InventoryRecord, snmp_engine: SnmpEngine) -> UsmUserData:
    location = os.path.join("secrets/snmpv3", ir.secret)  # type: ignore
    if os.path.exists(location):
        username = get_secret_value(location, "userName", required=True)

        auth_key = get_secret_value(location, "authKey", required=False)
        priv_key = get_secret_value(location, "privKey", required=False)

        auth_protocol = get_secret_value(location, "authProtocol", required=False)
        auth_protocol = AuthProtocolMap.get(auth_protocol.upper(), "NONE")

        priv_protocol = get_secret_value(
            location, "privProtocol", required=False, default="NONE"
        )
        priv_protocol = PrivProtocolMap.get(priv_protocol.upper(), "NONE")

        auth_key_type = int(
            get_secret_value(location, "authKeyType", required=False, default="0")
        )

        priv_key_type = int(
            get_secret_value(location, "privKeyType", required=False, default="0")
        )
        if (
            isinstance(ir.security_engine, str)
            and ir.security_engine != ""
            and not ir.security_engine.isdigit()
        ):
            security_engine_id = OctetString(hexValue=ir.security_engine)
            logger.debug(f"Security eng from profile {security_engine_id}")
        else:
            security_engine_id = get_security_engine_id(logger, ir, snmp_engine)
            logger.debug(f"Security eng dynamic {security_engine_id}")

        security_name = None
        logger.debug(
            f"{username},authKey={auth_key},privKey={priv_key},authProtocol={auth_protocol},privProtocol={priv_protocol},securityEngineId={security_engine_id},securityName={security_name},authKeyType={auth_key_type},privKeyType={priv_key_type}"
        )
        return UsmUserData(
            username,
            authKey=auth_key if auth_key else None,
            privKey=priv_key if priv_key else None,
            authProtocol=auth_protocol,
            privProtocol=priv_protocol,
            securityEngineId=security_engine_id,
            securityName=security_name,
            authKeyType=auth_key_type,
            privKeyType=priv_key_type,
        )

    else:
        raise FileNotFoundError(f"invalid username from secret {ir.secret}")


def get_auth_v2c(ir: InventoryRecord) -> CommunityData:
    return CommunityData(ir.community, mpModel=1)


def get_auth_v1(ir: InventoryRecord) -> CommunityData:
    return CommunityData(ir.community, mpModel=0)


def get_auth(
    logger, ir: InventoryRecord, snmp_engine: SnmpEngine
) -> Union[UsmUserData, CommunityData]:
    if ir.version == "1":
        return get_auth_v1(ir)
    elif ir.version == "2c":
        return get_auth_v2c(ir)
    else:
        return get_auth_v3(logger, ir, snmp_engine)
