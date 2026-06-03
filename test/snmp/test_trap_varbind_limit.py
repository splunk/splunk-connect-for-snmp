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
import os
from unittest import TestCase
from unittest.mock import patch

from splunk_connect_for_snmp.snmp.trap_varbind_limit import (
    TRAP_VARBIND_DECODE_DEFAULT,
    TRAP_VARBIND_DECODE_MIN,
    limit_trap_varbind_pairs,
    parse_max_trap_varbinds_to_decode,
)


class TestParseMaxTrapVarbindsToDecode(TestCase):
    def test_default_unlimited(self):
        self.assertEqual(
            TRAP_VARBIND_DECODE_DEFAULT, parse_max_trap_varbinds_to_decode("")
        )

    def test_zero_means_unlimited(self):
        self.assertEqual(0, parse_max_trap_varbinds_to_decode("0"))

    def test_positive_limit(self):
        self.assertEqual(100, parse_max_trap_varbinds_to_decode("100"))

    def test_clamps_negative_to_minimum(self):
        self.assertEqual(
            TRAP_VARBIND_DECODE_MIN, parse_max_trap_varbinds_to_decode("-5")
        )

    def test_invalid_uses_default(self):
        self.assertEqual(
            TRAP_VARBIND_DECODE_DEFAULT,
            parse_max_trap_varbinds_to_decode("not-a-number"),
        )

    def test_env_override(self):
        with patch.dict(os.environ, {"MAX_TRAP_VARBINDS_TO_DECODE": "100"}):
            self.assertEqual(100, parse_max_trap_varbinds_to_decode())


class TestLimitTrapVarbindPairs(TestCase):
    @patch(
        "splunk_connect_for_snmp.snmp.trap_varbind_limit.MAX_TRAP_VARBINDS_TO_DECODE",
        0,
    )
    def test_unlimited_returns_all_pairs(self):
        pairs = [("1", "a"), ("2", "b"), ("3", "c"), ("4", "d")]
        self.assertEqual(pairs, limit_trap_varbind_pairs(pairs))

    @patch(
        "splunk_connect_for_snmp.snmp.trap_varbind_limit.MAX_TRAP_VARBINDS_TO_DECODE",
        3,
    )
    def test_limits_pairs(self):
        pairs = [("1", "a"), ("2", "b"), ("3", "c"), ("4", "d")]
        self.assertEqual(pairs[:3], limit_trap_varbind_pairs(pairs))

    @patch(
        "splunk_connect_for_snmp.snmp.trap_varbind_limit.MAX_TRAP_VARBINDS_TO_DECODE",
        1,
    )
    def test_minimum_one_varbind_when_limited(self):
        pairs = [("1", "a"), ("2", "b")]
        self.assertEqual([("1", "a")], limit_trap_varbind_pairs(pairs))

    @patch(
        "splunk_connect_for_snmp.snmp.trap_varbind_limit.MAX_TRAP_VARBINDS_TO_DECODE",
        2,
    )
    def test_logs_when_varbinds_truncated(self):
        pairs = [("1", "a"), ("2", "b"), ("3", "c")]
        test_logger = logging.getLogger("test.trap_varbind_limit")
        with self.assertLogs(test_logger, level="INFO") as captured:
            result = limit_trap_varbind_pairs(pairs, log=test_logger, source="10.0.0.1")
        self.assertEqual(pairs[:2], result)
        self.assertTrue(
            any("decoding first 2" in message for message in captured.output)
        )
