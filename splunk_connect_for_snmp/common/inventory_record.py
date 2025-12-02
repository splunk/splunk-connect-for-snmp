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
from typing import List, Union

from pydantic import validator

from splunk_connect_for_snmp.common.base_record import BaseRecord
from splunk_connect_for_snmp.common.hummanbool import human_bool

InventoryStr = Union[None, str]
InventoryInt = Union[None, int]
InventoryBool = Union[None, bool]

ALTERNATIVE_FIELDS = {
    "securityEngine": "security_engine",
    "SmartProfiles": "smart_profiles",
}


class InventoryRecord(BaseRecord):
    walk_interval: InventoryInt = 42000
    profiles: List
    smart_profiles: InventoryBool
    delete: InventoryBool
    group: InventoryStr

    def __init__(self, *args, **kwargs):
        for old, current in ALTERNATIVE_FIELDS.items():
            if old in kwargs.keys():
                kwargs[current] = kwargs.get(old)
                kwargs.pop(old, None)
        super().__init__(*args, **kwargs)

    @validator("walk_interval", pre=True)
    def walk_interval_validator(cls, value):
        if not value:
            return 42000
        v = int(value)
        if v < 1800:
            return 1800
        elif v > 604800:
            return 604800
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

    @validator("group", pre=True)
    def group_validator(cls, value):
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return False
        else:
            return value
