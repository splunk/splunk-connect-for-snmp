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
import sys
import time
import typing
from typing import Union

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError


def human_bool(flag: Union[str, bool], default: bool = False) -> bool:

    if flag is None:
        return False

    if isinstance(flag, bool):
        return flag

    if flag.lower() in [
        "true",
        "1",
        "t",
        "y",
        "yes",
    ]:
        return True
    elif flag.lower() in [
        "false",
        "0",
        "f",
        "n",
        "no",
    ]:
        return False
    else:
        return default


class BadlyFormattedFieldError(Exception):
    pass


def convert_to_float(value: typing.Any, ignore_error: bool = False) -> typing.Any:
    try:
        return float(value)
    except ValueError:
        if ignore_error:
            return value
        raise BadlyFormattedFieldError(f"Value '{value}' should be numeric")


def disable_mongo_logging():
    logging.getLogger("mongo").setLevel(logging.CRITICAL)
    logging.getLogger("pymongo").setLevel(logging.CRITICAL)


def wait_for_mongodb_replicaset(logger, max_retries=120, retry_interval=5):
    """
    Wait for MongoDB to be ready before starting the application.
    For replica sets, waits for PRIMARY to be elected.
    """
    mongo_mode = os.getenv("MONGODB_MODE", "standalone").lower()
    if mongo_mode == "standalone":
        logger.info("MongoDB is in standalone mode, skipping ReplicaSet wait")
        return

    mongo_uri = os.getenv("MONGO_URI")

    if not mongo_uri:
        logger.warning("⚠️  MONGO_URI not set, exiting application")
        sys.exit(1)

    logger.info(f"Waiting for MongoDB ReplicaSet to be ready and elect the primary...")

    for attempt in range(1, max_retries + 1):
        try:
            # Try to connect
            client = MongoClient(
                mongo_uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000
            )

            # Execute a simple operation to verify PRIMARY exists
            client.admin.command("ping")

            # For replica sets, verify PRIMARY exists
            if "replicaSet=" in mongo_uri:
                if client.primary is None:
                    raise Exception("No PRIMARY elected yet")
                logger.info(f"  ✅ PRIMARY found: {client.primary}")

            client.close()
            logger.info("✅ MongoDB is ready")
            return

        except (ServerSelectionTimeoutError, ConnectionFailure, Exception) as e:
            if attempt >= max_retries:
                logger.info(
                    f"❌ MongoDB not ready after {max_retries * retry_interval}s"
                )
                logger.info(f"   Error: {e}")
                sys.exit(1)

            if attempt % 6 == 0:  # Print every 30 seconds
                logger.info(
                    f"  Still waiting... ({attempt}/{max_retries}) - {e.__class__.__name__}"
                )

            time.sleep(retry_interval)
