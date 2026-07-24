#   ########################################################################
#   Copyright 2021 Splunk Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
#   ########################################################################
import logging

import pytest

from integration_tests.utils.splunk_test_utils import (
    configure_local_mibs_compose,
    configure_local_mibs_microk8s,
    fetch_mib_index_compose,
    fetch_mib_index_microk8s,
    get_mibserver_logs_compose,
    get_mibserver_logs_microk8s,
    wait_for_containers_initialization,
    wait_for_pod_initialization_microk8s,
)

logger = logging.getLogger(__name__)

CUSTOM_MIB_NAME = "SC4SNMP-TEST-MIB"
PERMISSION_ERROR_MARKERS = ("Permission denied", "Errno 13")


@pytest.mark.part5
class TestLocalMibs:
    def test_local_mib_loaded_without_permission_error(self, request, setup_splunk):
        deployment = request.config.getoption("sc4snmp_deployment")

        if deployment == "microk8s":
            configure_local_mibs_microk8s()
            wait_for_pod_initialization_microk8s()
            index = fetch_mib_index_microk8s()
            logs = get_mibserver_logs_microk8s()
        else:
            configure_local_mibs_compose()
            wait_for_containers_initialization()
            index = fetch_mib_index_compose()
            logs = get_mibserver_logs_compose()

        logger.info(f"mibserver index.csv snippet: {index[:500]}")

        # Loaded correctly: the custom MIB must show up in the compiled/served index.
        assert CUSTOM_MIB_NAME in index, (
            f"{CUSTOM_MIB_NAME} was not found in the mibserver index; "
            f"local MIB was not compiled/served."
        )

        # No permission issue: the mibserver logs must not report a read/write failure
        # while compiling the local MIBs directory.
        for marker in PERMISSION_ERROR_MARKERS:
            assert marker not in logs, (
                f"mibserver logs contain '{marker}', indicating a permission "
                f"issue while loading local MIBs"
            )
