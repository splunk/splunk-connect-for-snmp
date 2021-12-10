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
# from dataclasses import dataclass
import dataclasses
import inspect
import json
import socket
from dataclasses import InitVar, dataclass, field
from ipaddress import IPv4Address, IPv6Address
from typing import Dict, List, Optional, Union
from urllib.parse import urlparse

from splunk_connect_for_snmp.common.hummanbool import human_bool


@dataclass(repr=True)
class InventoryRecord:
    # address,port,version,community,secret,securityEngine,walk_interval,profiles,SmartProfiles,delete
    _id: InitVar[int] = field(init=False, repr=False, default=0)
    address: str
    _address: str = field(init=False, repr=False)

    @property
    def address(self) -> str:
        return self._address

    @address.setter
    def address(self, value: str):
        if value is None:
            raise ValueError(f"field address cannot be null")
        if value.startswith("#"):
            raise ValueError(f"field address cannot be commented")
        else:
            test = None
            try:
                test = IPv4Address(value)
                test = IPv6Address(value)
            except ValueError:
                pass
            if test is None:
                try:
                    socket.gethostbyname_ex(value)
                    test = value
                except socket.gaierror:
                    raise ValueError(
                        f"field address must be an IP or a resolvable hostname {self}"
                    )
            if test is None:
                raise ValueError(
                    f"field address must be an IP or a resolvable hostname {self}"
                )

            self._address = value

    port: int
    _port: int = field(init=False, repr=False)

    @property
    def port(self) -> int:
        return self._port

    @port.setter
    def port(self, value):
        if value == None or (isinstance(value, str) and value.strip() == ""):
            self._port = 161
        else:
            if not isinstance(value, int):
                value = int(value)

            if value < 1 or value > 65535:
                raise ValueError(f"Port out of range {value}")
            self._port = value

    version: str
    _version: str = field(init=False, repr=False)

    @property
    def version(self) -> str:
        return self._version

    @version.setter
    def version(self, value):
        if value == None or value.strip() == "":
            self._version = "2c"
        else:
            if value not in ("2c", "3"):
                raise ValueError(f"version out of range {value} accepted is 2c or 3")
            self._version = value

    community: str
    _community: str = field(init=False, repr=False)

    @property
    def community(self) -> str:
        return self._community

    @community.setter
    def community(self, value):
        if value == None or (isinstance(value, str) and value.strip() == ""):
            self._community = None
        else:
            self._community = value

    secret: str
    _secret: str = field(init=False, repr=False)

    @property
    def secret(self) -> str:
        return self._secret

    @secret.setter
    def secret(self, value):
        if value == None or (isinstance(value, str) and value.strip() == ""):
            self._secret = None
        else:
            self._secret = value

    securityEngine: str
    _securityEngine: str = field(init=False, repr=False, default=None)

    @property
    def securityEngine(self) -> str:
        return self._securityEngine

    @securityEngine.setter
    def securityEngine(self, value):
        if value == None or (isinstance(value, str) and value.strip() == ""):
            self._securityEngine = None
        else:
            self._securityEngine = value

    walk_interval: int
    _walk_interval: int = field(init=False, repr=False, default=4200)

    @property
    def walk_interval(self) -> int:
        return self._walk_interval

    @walk_interval.setter
    def walk_interval(self, value):
        if value == None:
            self._walk_interval = 42000
        v = int(value)
        if v < 1800:
            self._walk_interval = 1800
        if v > 42000:
            self._walk_interval = 42000

    profiles: List[str] = []
    _profiles: List[str] = field(init=False, repr=False)

    @property
    def profiles(self) -> List[str]:
        return self._profiles

    @profiles.setter
    def profiles(self, value):
        if value == None or (isinstance(value, str) and value.strip() == ""):
            self._profiles = []
        elif isinstance(value, str):
            self._profiles = value.split(";")
        else:
            self._profiles = value

    SmartProfiles: bool = True
    _SmartProfiles: bool = field(init=False, repr=False)

    @property
    def SmartProfiles(self) -> bool:
        return self._SmartProfiles

    @SmartProfiles.setter
    def SmartProfiles(self, value):
        if value == None or (isinstance(value, str) and value.strip() == ""):
            self._SmartProfiles = True
        else:
            self._SmartProfiles = human_bool(value)

    delete: bool = False
    _delete: bool = field(init=False, repr=False)

    @property
    def delete(self) -> bool:
        return self._delete

    @delete.setter
    def delete(self, value):
        if value == None or (isinstance(value, str) and value.strip() == ""):
            self._delete = False
        else:
            self._delete = human_bool(value)

    @staticmethod
    def from_json(ir_json: str):
        ir_dict = json.loads(ir_json)
        return InventoryRecord(**ir_dict)

    def tojson(self):
        return {
            "address": self.address,
            "port": self.port,
            "version": self.version,
            "community": self.community,
            "secret": self.secret,
            "securityEngine": self.securityEngine,
            "walk_interval": self.walk_interval,
            "profiles": self.profiles,
            "SmartProfiles": self.SmartProfiles,
            "delete": self.delete,
        }

    @classmethod
    def from_dict(cls, env):
        return cls(
            **{k: v for k, v in env.items() if k in inspect.signature(cls).parameters}
        )

    def asdict(self) -> dict:
        newDict = dict()
        # Iterate over all the items in dictionary and filter items which has even keys
        for (key, value) in dataclasses.asdict(self).items():
            # Check if key is even then add pair to new dictionary
            if not key.startswith("_") and value is not None:
                newDict[key] = value

        return newDict


class InventoryRecordEncoder(json.JSONEncoder):
    def default(self, o):
        if "tojson" in dir(o):
            return o.tojson()
        return json.JSONEncoder.default(self, o)
