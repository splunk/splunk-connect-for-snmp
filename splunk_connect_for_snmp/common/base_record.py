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
import socket
from ipaddress import ip_address
from typing import Union

from pydantic import BaseModel, validator

RecordStr = Union[None, str]
RecordInt = Union[None, int]


class BaseRecord(BaseModel):
    """Base class for common SNMP record fields"""

    address: RecordStr
    port: RecordInt = 161
    version: RecordStr
    community: RecordStr
    secret: RecordStr
    security_engine: RecordStr = ""

    @validator("address", pre=True)
    def address_validator(cls, value, values):
        if not value:
            raise ValueError("field address cannot be null")
        if value.startswith("#"):
            raise ValueError("field address cannot be commented")
        else:
            try:
                ip_address(value)
            except ValueError:
                try:
                    socket.getaddrinfo(value, values["port"])
                except socket.gaierror:
                    raise ValueError(
                        f"field address must be an IP or a resolvable hostname {value}"
                    )

            return value

    @validator("port", pre=True)
    def port_validator(cls, value):
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return 161
        else:
            if not isinstance(value, int):
                value = int(value)
            if value < 1 or value > 65535:
                raise ValueError(f"Port out of range {value}")
            return value

    @validator("version", pre=True)
    def version_validator(cls, value):
        if value is None or value.strip() == "":
            return "2c"
        else:
            if value not in ("1", "2c", "3"):
                raise ValueError(
                    f"version out of range {value} accepted is 1 or 2c or 3"
                )
            return value

    @validator("community", "secret", "security_engine", pre=True)
    def community_secret_security_engine_validator(cls, value):
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None
        else:
            return value

    def asdict(self) -> dict:
        return self.dict()
