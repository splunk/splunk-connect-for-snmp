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
import json
from dataclasses import dataclass
from typing import List


@dataclass
class InventoryRecord:
    #ip,version,community,walk_interval,profiles,SmartProfiles,delete
    ip: str
    version: str
    community: str
    walk_interval: str
    profiles: List
    SmartProfiles: bool
    delete: bool

    def __post_init__(self):
        if self.delete is None:
            self.delete = False

    def to_json(self) -> str:
        return json.dumps(self, default=lambda o: o.__dict__)

    @staticmethod
    def from_json(ir_json: str):
        ir_dict = json.loads(ir_json)
        return InventoryRecord(**ir_dict)