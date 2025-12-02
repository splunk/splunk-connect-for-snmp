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

from pydantic import validator

from splunk_connect_for_snmp.common.base_record import BaseRecord
from splunk_connect_for_snmp.common.hummanbool import human_bool

DiscoveryStr = Union[None, str]
DiscoveryInt = Union[None, int]
DiscoveryBool = Union[None, bool]
DiscoveryList = Union[None, List[dict]]


class DiscoveryRecord(BaseRecord):
    discovery_name: DiscoveryStr
    network_address: DiscoveryStr
    frequency: DiscoveryInt
    delete_already_discovered: DiscoveryBool
    device_rules: DiscoveryList

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

    @validator("delete_already_discovered", pre=True)
    def delete_already_discovered_validator(cls, value):
        if value is None:
            return False
        return human_bool(value)
