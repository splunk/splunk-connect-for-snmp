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

from ipaddress import ip_network
from typing import List, Union

from pydantic import BaseModel, validator

from splunk_connect_for_snmp.common.hummanbool import human_bool

DiscoveryStr = Union[None, str]
DiscoveryInt = Union[None, int]
DiscoveryBool = Union[None, bool]
DiscoveryList = Union[None, List[dict]]


class DiscoveryRecord(BaseModel):
    discovery_name: DiscoveryStr
    network_address: DiscoveryStr
    address: DiscoveryStr
    port: DiscoveryInt = 161
    version: DiscoveryStr
    community: DiscoveryStr
    secret: DiscoveryStr
    security_engine: DiscoveryStr = ""
    frequency: DiscoveryInt
    delete_already_discovered: DiscoveryBool
    skip_active_check: DiscoveryBool
    device_rules: DiscoveryList
    is_ipv6: DiscoveryBool

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @validator("network_address", pre=True)
    def network_address_validator(cls, value):
        if value is None:
            raise ValueError("field network address cannot be null")
        else:
            try:
                ip_network(value, strict=False)
            except ValueError:
                raise ValueError(f"field network address must be an valid subnet")

            return value

    @validator("port", pre=True)
    def port_validator(cls, value):
        if value is None:
            return 161
        if isinstance(value, int) and value >= 1 or value <= 65535:
            return value
        else:
            raise ValueError("field port must be an integer between 1 and 65535")

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
        return value

    @validator("frequency", pre=True)
    def frequency_validator(cls, value):
        if value is None:
            return 86400
        elif value < 21600:
            return 21600

        return value

    @validator("device_rules", pre=True)
    def device_rules_validator(cls, value):
        if value is None or (isinstance(value, list) and value == []):
            return None
        return value

    @validator("delete_already_discovered", "skip_active_check", pre=True)
    def delete_already_discovered_skip_active_check_validator(cls, value):
        if value is None:
            return False
        return human_bool(value)

    def asdict(self) -> dict:
        return self.dict()
