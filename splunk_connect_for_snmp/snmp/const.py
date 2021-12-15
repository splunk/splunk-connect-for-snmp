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
from pysnmp.entity import config

AuthProtocolMap = {
    "MD5": config.usmHMACMD5AuthProtocol,
    "SHA": config.usmHMACSHAAuthProtocol,
    "SHA224": config.usmHMAC128SHA224AuthProtocol,
    "SHA256": config.usmHMAC192SHA256AuthProtocol,
    "SHA384": config.usmHMAC256SHA384AuthProtocol,
    "SHA512": config.usmHMAC384SHA512AuthProtocol,
    "NONE": config.usmNoAuthProtocol,
}

PrivProtocolMap = {
    "DES": config.usmDESPrivProtocol,
    "3DES": config.usm3DESEDEPrivProtocol,
    "AES": config.usmAesCfb128Protocol,
    "AES128": config.usmAesCfb128Protocol,
    "AES192": config.usmAesCfb192Protocol,
    "AES192BLMT": config.usmAesBlumenthalCfb192Protocol,
    "AES256": config.usmAesCfb256Protocol,
    "AES256BLMT": config.usmAesBlumenthalCfb256Protocol,
    "NONE": config.usmNoPrivProtocol,
}

DEFAULT_POLLING_FREQUENCY = 60
