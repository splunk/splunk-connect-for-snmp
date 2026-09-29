#
# Copyright 2026 Splunk Inc.
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

"""One lazily created MongoDB client per process.

Celery constructs task instances before forking its worker children. Keeping the
client here, rather than on a task during construction, avoids inheriting a
MongoClient whose monitoring threads belong to the parent process.
"""

import atexit
import os

from pymongo import MongoClient

_client: MongoClient | None = None
_client_pid: int | None = None


def get_mongo_client() -> MongoClient:
    global _client, _client_pid

    pid = os.getpid()
    if _client_pid != pid:
        # An inherited client must never be used in a forked child.
        _client = None
        _client_pid = pid
    if _client is None:
        _client = MongoClient(os.getenv("MONGO_URI"))
    return _client


def close_mongo_client() -> None:
    global _client, _client_pid

    client = _client if _client_pid == os.getpid() else None
    _client = None
    _client_pid = None
    if client is not None:
        client.close()


atexit.register(close_mongo_client)
