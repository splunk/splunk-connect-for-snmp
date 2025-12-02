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
from pymongo.errors import ServerSelectionTimeoutError, ConnectionFailure


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
    mongo_mode = os.getenv('MONGODB_MODE', 'standalone').lower()
    if mongo_mode == "standalone":
        logger.info("MongoDB standalone: no ReplicaSet waiting needed.")
        return

    mongo_uri = os.getenv('MONGO_URI')
    if not mongo_uri:
        logger.error("MONGO_URI not set!")
        sys.exit(1)

    # URI without credentials for topology discovery
    noauth_uri = mongo_uri.split("@")[-1]
    noauth_uri = "mongodb://" + noauth_uri

    logger.info("Waiting for MongoDB ReplicaSet PRIMARY...")

    for attempt in range(1, max_retries + 1):
        try:
            # First try with credentials (works after user exists)
            try:
                client = MongoClient(mongo_uri, serverSelectionTimeoutMS=4000)
                client.admin.command("ping")
                if client.primary:
                    logger.info(f"PRIMARY found (auth): {client.primary}")
                    return
            except Exception:
                pass  # ignore and retry no-auth method

            # Now try WITHOUT auth to detect PRIMARY (works earlier)
            client = MongoClient(noauth_uri, serverSelectionTimeoutMS=4000)
            primary = client.primary
            if primary:
                logger.info(f"PRIMARY detected (no-auth): {primary}")
                # Give time for user-creation job
                time.sleep(5)
                return

        except Exception as e:
            if attempt == max_retries:
                logger.error(f"MongoDB Replicaset not ready: {e}")
                sys.exit(1)

        time.sleep(retry_interval)
        if attempt % 6 == 0:
            logger.info(f"Still waiting... ({attempt}/{max_retries})")