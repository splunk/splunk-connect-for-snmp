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
import inspect
import json
import socket
from ipaddress import ip_address
from typing import List, Union

from pydantic import BaseModel, validator

from splunk_connect_for_snmp.common.hummanbool import human_bool

InventoryStr = Union[None, str]
InventoryInt = Union[None, int]
InventoryBool = Union[None, bool]

ALTERNATIVE_FIELDS = {
    "securityEngine": "security_engine",
    "SmartProfiles": "smart_profiles",
}


class InventoryRecord(BaseModel):
    address: InventoryStr
    port: InventoryInt = 161
    version: InventoryStr
    community: InventoryStr
    secret: InventoryStr
    security_engine: InventoryStr = ""
    walk_interval: InventoryInt = 42000
    profiles: List
    smart_profiles: InventoryBool
    delete: InventoryBool

    def __init__(self, *args, **kwargs):
        for old, current in ALTERNATIVE_FIELDS.items():
            if old in kwargs.keys():
                kwargs[current] = kwargs.get(old)
                kwargs.pop(old, None)
        super().__init__(*args, **kwargs)

    @validator("address", pre=True)
    def address_validator(cls, value):
        if value is None:
            raise ValueError("field address cannot be null")
        if value.startswith("#"):
            raise ValueError("field address cannot be commented")
        else:
            try:
                ip_address(value)
            except ValueError:
                try:
                    socket.gethostbyname_ex(value)
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

    @validator("community", pre=True)
    def community_validator(cls, value):
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None
        else:
            return value

    @validator("secret", pre=True)
    def secret_validator(cls, value):
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None
        else:
            return value

    @validator("security_engine", pre=True)
    def security_engine_validator(cls, value):
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None
        else:
            return value

    @validator("walk_interval", pre=True)
    def walk_interval_validator(cls, value):
        if not value:
            return 42000
        v = int(value)
        if v < 1800:
            return 1800
        elif v > 42000:
            return 42000
        else:
            return v

    @validator("profiles", pre=True)
    def profiles_validator(cls, value):
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return []
        elif isinstance(value, str):
            return value.split(";")
        else:
            return value

    @validator("smart_profiles", pre=True)
    def smart_profiles_validator(cls, value):
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return True
        else:
            return human_bool(value)

    @validator("delete", pre=True)
    def delete_validator(cls, value):
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return False
        else:
            return human_bool(value)

    @classmethod
    def from_dict(cls, env):
        return cls(
            **{k: v for k, v in env.items() if k in inspect.signature(cls).parameters}
        )

    def asdict(self) -> dict:
        return self.dict()


class InventoryRecordEncoder(json.JSONEncoder):
    def default(self, o):
        if "tojson" in dir(o):
            return o.tojson()
        return json.JSONEncoder.default(self, o)
