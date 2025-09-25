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
    "MD5": config.USM_AUTH_HMAC96_MD5,
    "SHA": config.USM_AUTH_HMAC96_SHA,
    "SHA224": config.USM_AUTH_HMAC128_SHA224,
    "SHA256": config.USM_AUTH_HMAC192_SHA256,
    "SHA384": config.USM_AUTH_HMAC256_SHA384,
    "SHA512": config.USM_AUTH_HMAC384_SHA512,
    "NONE": config.USM_AUTH_NONE,
}

PrivProtocolMap = {
    "DES": config.USM_PRIV_CBC56_DES,
    "3DES": config.USM_PRIV_CBC168_3DES,
    "AES": config.USM_PRIV_CFB192_AES,
    "AES128": config.USM_PRIV_CFB192_AES,
    "AES192": config.USM_PRIV_CFB192_AES,
    "AES192BLMT": config.USM_PRIV_CFB192_AES_BLUMENTHAL,
    "AES256": config.USM_PRIV_CFB256_AES,
    "AES256BLMT": config.USM_PRIV_CFB256_AES_BLUMENTHAL,
    "NONE": config.USM_PRIV_NONE,
}

DEFAULT_POLLING_FREQUENCY = 60
