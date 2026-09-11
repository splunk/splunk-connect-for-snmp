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
import csv
from io import StringIO
from typing import Any, Dict, Optional, Tuple

from celery.utils.log import get_task_logger
from requests import Response
from requests.exceptions import RequestException

logger = get_task_logger(__name__)


class MibIndexResponseValidator:
    """Validate a MIB index response and retain its parse result for one refresh."""

    def __init__(self) -> None:
        self._parsed_content: Optional[bytes] = None
        self._parsed_encoding: Optional[str] = None
        self._parsed_result: Optional[Tuple[Dict[str, str], int]] = None

    @staticmethod
    def parse_mib_index(index_content: str) -> Tuple[Dict[str, str], int]:
        """
        Parse the MIB index into the mapping used to resolve OID prefixes.

        Each two-column row contains the MIB module name followed by its OID
        prefix. Values are kept as supplied, rows with any other number of columns
        are skipped, and duplicate OID prefixes retain the last mapping. If CSV
        parsing fails, mappings read before the failure are preserved.

        :param index_content: Text returned by the MIB index endpoint

        :return: OID-prefix-to-MIB mapping and the number of malformed rows
        """
        parsed_map: Dict[str, str] = {}
        malformed_rows = 0

        try:
            with StringIO(index_content) as index_csv:
                reader = csv.reader(index_csv)
                for row in reader:
                    if len(row) != 2:
                        malformed_rows += 1
                        continue

                    mib = row[0].strip()
                    oid_prefix = row[1].strip()

                    if not mib or not oid_prefix:
                        malformed_rows += 1
                        continue

                    parsed_map[oid_prefix] = mib
        except csv.Error:
            malformed_rows += 1

        return parsed_map, malformed_rows

    def parse_response(self, response: Response) -> Tuple[Dict[str, str], int]:
        """
        Parse a MIB index response once during the current refresh.

        requests-cache may pass the same response through its hook more than
        once. The stored result is reused while the response body and encoding
        match. A different response, such as a stale fallback, is parsed
        separately.

        :param response: HTTP response containing the MIB index

        :return: OID-prefix-to-MIB mapping and the number of malformed rows
        """
        response_content = response.content
        response_encoding = response.encoding
        parsed_result = self._parsed_result
        parsed_now = False

        if (
            parsed_result is None
            or response_content != self._parsed_content
            or response_encoding != self._parsed_encoding
        ):
            logger.debug(
                f"Parsing MIB index response content_length={len(response_content)} "
                f"encoding={response_encoding}"
            )
            parsed_result = MibIndexResponseValidator.parse_mib_index(response.text)
            self._parsed_content = response_content
            self._parsed_encoding = response_encoding
            self._parsed_result = parsed_result
            parsed_now = True

        logger.debug(
            f"MIB index parse result ready parsed_now={parsed_now} "
            f"valid_mappings={len(parsed_result[0])} "
            f"malformed_rows={parsed_result[1]}"
        )

        return parsed_result

    def __call__(self, response: Response, *args: Any, **kwargs: Any) -> Response:
        """
        Validate a live MIB index response before requests-cache stores it.

        Cached and non-success responses are returned unchanged. Raising
        ``RequestException`` for an invalid live response prevents it from
        replacing the cached index and lets ``stale_if_error`` return the last
        usable response when one is available.

        :param response: HTTP response returned by the MIB index endpoint
        :param args: Additional positional arguments supplied to the hook
        :param kwargs: Additional keyword arguments supplied to the hook

        :return: Original HTTP response after validation

        :raises RequestException: If a live successful response has no mappings
        """
        if response.status_code != 200 or bool(getattr(response, "from_cache", False)):
            return response

        parsed_map, malformed_rows = self.parse_response(response)
        if not parsed_map:
            logger.error(
                f"Live MIB index response rejected before caching "
                f"status={response.status_code} valid_mappings=0 "
                f"malformed_rows={malformed_rows}"
            )
            raise RequestException(
                "MIB index contains no valid mappings "
                f"(malformed_rows={malformed_rows})",
                response=response,
            )
        return response
