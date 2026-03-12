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
from unittest import TestCase
from unittest.mock import mock_open, patch

from splunk_connect_for_snmp.splunk.tasks import _read_hec_token


class TestReadHecToken(TestCase):
    """Unit tests for _read_hec_token()."""

    @patch("splunk_connect_for_snmp.splunk.tasks.os.getenv")
    def test_returns_env_token_when_no_file_set(self, mock_getenv):
        def getenv(key, default=None):
            if key == "SPLUNK_HEC_TOKEN_FILE":
                return None
            if key == "SPLUNK_HEC_TOKEN":
                return "env-token-123"
            return default

        mock_getenv.side_effect = getenv
        result = _read_hec_token()
        self.assertEqual(result, "env-token-123")

    @patch("splunk_connect_for_snmp.splunk.tasks.os.getenv")
    def test_returns_none_when_no_file_and_no_env_token(self, mock_getenv):
        def getenv(key, default=None):
            if key == "SPLUNK_HEC_TOKEN_FILE":
                return None
            if key == "SPLUNK_HEC_TOKEN":
                return None
            return default

        mock_getenv.side_effect = getenv
        result = _read_hec_token()
        self.assertIsNone(result)

    @patch("splunk_connect_for_snmp.splunk.tasks.os.path.isfile")
    @patch("splunk_connect_for_snmp.splunk.tasks.os.getenv")
    def test_returns_token_from_file_when_file_exists_and_has_content(
        self, mock_getenv, mock_isfile
    ):
        def getenv(key, default=None):
            if key == "SPLUNK_HEC_TOKEN_FILE":
                return "/run/secrets/splunk_hec_token"
            if key == "SPLUNK_HEC_TOKEN":
                return "env-fallback"
            return default

        mock_getenv.side_effect = getenv
        mock_isfile.return_value = True
        with patch(
            "splunk_connect_for_snmp.splunk.tasks.open",
            mock_open(read_data="  file-token-456  \n"),
        ):
            result = _read_hec_token()
        self.assertEqual(result, "file-token-456")

    @patch("splunk_connect_for_snmp.splunk.tasks.logger")
    @patch("splunk_connect_for_snmp.splunk.tasks.os.path.isfile")
    @patch("splunk_connect_for_snmp.splunk.tasks.os.getenv")
    def test_falls_back_to_env_when_file_empty(
        self, mock_getenv, mock_isfile, mock_logger
    ):
        def getenv(key, default=None):
            if key == "SPLUNK_HEC_TOKEN_FILE":
                return "/run/secrets/splunk_hec_token"
            if key == "SPLUNK_HEC_TOKEN":
                return "env-token"
            return default

        mock_getenv.side_effect = getenv
        mock_isfile.return_value = True
        with patch(
            "splunk_connect_for_snmp.splunk.tasks.open",
            mock_open(read_data="   \n"),
        ):
            result = _read_hec_token()
        self.assertEqual(result, "env-token")
        mock_logger.warning.assert_called_once()
        self.assertIn("file is empty", mock_logger.warning.call_args[0][0])
        self.assertIn("SPLUNK_HEC_TOKEN_FILE", mock_logger.warning.call_args[0][0])

    @patch("splunk_connect_for_snmp.splunk.tasks.os.path.isfile")
    @patch("splunk_connect_for_snmp.splunk.tasks.os.getenv")
    def test_falls_back_to_env_when_file_does_not_exist(self, mock_getenv, mock_isfile):
        def getenv(key, default=None):
            if key == "SPLUNK_HEC_TOKEN_FILE":
                return "/nonexistent/path"
            if key == "SPLUNK_HEC_TOKEN":
                return "env-token"
            return default

        mock_getenv.side_effect = getenv
        mock_isfile.return_value = False
        result = _read_hec_token()
        self.assertEqual(result, "env-token")

    @patch("splunk_connect_for_snmp.splunk.tasks.os.path.isfile")
    @patch("splunk_connect_for_snmp.splunk.tasks.os.getenv")
    def test_falls_back_to_env_on_oserror_reading_file(self, mock_getenv, mock_isfile):
        def getenv(key, default=None):
            if key == "SPLUNK_HEC_TOKEN_FILE":
                return "/run/secrets/splunk_hec_token"
            if key == "SPLUNK_HEC_TOKEN":
                return "env-fallback"
            return default

        mock_getenv.side_effect = getenv
        mock_isfile.return_value = True
        with patch(
            "splunk_connect_for_snmp.splunk.tasks.open",
            side_effect=OSError("Permission denied"),
        ):
            result = _read_hec_token()
        self.assertEqual(result, "env-fallback")

    @patch("splunk_connect_for_snmp.splunk.tasks.logger")
    @patch("splunk_connect_for_snmp.splunk.tasks.os.path.isfile")
    @patch("splunk_connect_for_snmp.splunk.tasks.os.getenv")
    def test_returns_none_when_file_empty_and_no_env_token(
        self, mock_getenv, mock_isfile, mock_logger
    ):
        def getenv(key, default=None):
            if key == "SPLUNK_HEC_TOKEN_FILE":
                return "/run/secrets/splunk_hec_token"
            if key == "SPLUNK_HEC_TOKEN":
                return None
            return default

        mock_getenv.side_effect = getenv
        mock_isfile.return_value = True
        with patch(
            "splunk_connect_for_snmp.splunk.tasks.open",
            mock_open(read_data=""),
        ):
            result = _read_hec_token()
        self.assertIsNone(result)
        mock_logger.warning.assert_called_once()
        self.assertIn("file is empty", mock_logger.warning.call_args[0][0])

    @patch("splunk_connect_for_snmp.splunk.tasks.os.path.isfile")
    @patch("splunk_connect_for_snmp.splunk.tasks.os.getenv")
    def test_file_token_takes_precedence_over_env(self, mock_getenv, mock_isfile):
        def getenv(key, default=None):
            if key == "SPLUNK_HEC_TOKEN_FILE":
                return "/run/secrets/splunk_hec_token"
            if key == "SPLUNK_HEC_TOKEN":
                return "env-token-ignored"
            return default

        mock_getenv.side_effect = getenv
        mock_isfile.return_value = True
        with patch(
            "splunk_connect_for_snmp.splunk.tasks.open",
            mock_open(read_data="token-from-file"),
        ):
            result = _read_hec_token()
        self.assertEqual(result, "token-from-file")
