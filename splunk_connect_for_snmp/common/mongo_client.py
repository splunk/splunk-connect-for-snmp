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
import os

import pymongo

_mongo_client: pymongo.MongoClient | None = None


def get_mongo_client() -> pymongo.MongoClient:
    """Return the process-wide MongoClient, creating it on first use.

    Must be called only from code that runs after the Celery prefork pool has
    forked (i.e. from within a task body, or from the worker_process_init
    signal) - never from a Task.__init__, which runs once in the master
    before any child is forked.
    """
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = pymongo.MongoClient(os.getenv("MONGO_URI"))
    return _mongo_client


def close_mongo_client() -> None:
    global _mongo_client
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None


def reset_mongo_client() -> None:
    """Drop the cached client without closing it - a test-only seam."""
    global _mongo_client
    _mongo_client = None
