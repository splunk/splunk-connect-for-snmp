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
# Support use of .env file for developers
from contextlib import suppress

with suppress(ImportError):
    from dotenv import load_dotenv

    load_dotenv()


import os

MONGO_DB = os.getenv("MONGO_DB", "sc4snmp")
MONGO_DB_SCHEDULES = os.getenv("MONGO_DB_SCHEDULES", "schedules")

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_CELERY_DATABASE = os.getenv("MONGO_DB_CELERY_DATABASE", MONGO_DB)

# broker
broker_url = os.getenv("CELERY_BROKER_URL")
# results config
result_backend = MONGO_URI
result_extended = True
mongodb_backend_settings = {"database": MONGO_DB_CELERY_DATABASE}

beat_scheduler = "celerybeatmongo.schedulers.MongoScheduler"
mongodb_scheduler_url = MONGO_URI
mongodb_scheduler_db = MONGO_DB_CELERY_DATABASE

# Optimization for long running tasks
# https://docs.celeryproject.org/en/stable/userguide/optimizing.html#reserve-one-task-at-a-time
task_acks_late = False
worker_prefetch_multiplier = 1

task_ignore_result = True
