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
import logging
import sys
from csv import DictReader

from splunk_connect_for_snmp.common.inventory_record import InventoryRecord
from splunk_connect_for_snmp.snmp.manager import Poller


log_level = "DEBUG"
logger = logging.getLogger(__name__)
logger.setLevel(log_level)

# writing to stdout
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(log_level)
logger.addHandler(handler)


def run_walk():
    poller = Poller(no_mongo=True)

    with open("inventory.csv", encoding="utf-8") as csv_file:
        # Dict reader will trust the header of the csv
        ir_reader = DictReader(csv_file)
        for source_record in ir_reader:
            address = source_record["address"]
            if address.startswith("#"):
                continue
            try:
                ir = InventoryRecord(**source_record)
                retry = True
                while retry:
                    retry, result = poller.do_work(ir, walk=True)
                    logger.debug(result)
            except Exception as e:
                logger.exception(e)


if __name__ == "__main__":
    run_walk()
