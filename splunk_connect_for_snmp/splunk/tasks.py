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
try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass

import json
import os
from typing import Union
from urllib.error import URLError
from urllib.parse import urlunsplit

from celery import Task, shared_task
from celery.utils.log import get_task_logger
from requests import ConnectionError, ConnectTimeout, ReadTimeout, Session, Timeout

from splunk_connect_for_snmp.common.hummanbool import human_bool

SPLUNK_HEC_SCHEME = os.getenv("SPLUNK_HEC_SCHEME", "https")
SPLUNK_HEC_HOST = os.getenv("SPLUNK_HEC_HOST", "127.0.0.1")
SPLUNK_HEC_PORT = os.getenv("SPLUNK_HEC_PORT", None)
SPLUNK_HEC_PATH = os.getenv("SPLUNK_HEC_PATH", "services/collector")

url = {}
url["scheme"] = SPLUNK_HEC_SCHEME
url["hostn_enc"] = SPLUNK_HEC_HOST
url["path"] = SPLUNK_HEC_PATH
if SPLUNK_HEC_PORT:
    url["port"] = ":" + SPLUNK_HEC_PORT
else:
    url["port"] = ""
url["query"] = None
url["frag"] = None

SPLUNK_HEC_URI = urlunsplit(
    (
        url["scheme"],
        (url["hostn_enc"]) + (url["port"]),
        url["path"],
        url["query"],
        url["frag"],
    )
)


SPLUNK_HEC_TOKEN = os.getenv("SPLUNK_HEC_TOKEN", None)
SPLUNK_HEC_INDEX_EVENTS = os.getenv("SPLUNK_HEC_INDEX_EVENTS", "netops")
SPLUNK_HEC_INDEX_METRICS = os.getenv("SPLUNK_HEC_INDEX_METRICS", "netmetrics")
if human_bool(os.getenv("SPLUNK_HEC_INSECURESSL", "yes"), default=True):
    SPLUNK_HEC_TLSVERIFY = False
else:
    SPLUNK_HEC_TLSVERIFY = True

logger = get_task_logger(__name__)

# Token is only appropriate if we are working direct with Splunk
if SPLUNK_HEC_TOKEN:
    SPLUNK_HEC_HEADERS = {"Authorization": f"Splunk {SPLUNK_HEC_TOKEN}"}
else:
    SPLUNK_HEC_HEADERS = None
SPLUNK_HEC_CHUNK_SIZE = int(os.getenv("SPLUNK_HEC_CHUNK_SIZE", "50"))


class HECTask(Task):
    def __init__(self):
        self.session = Session()
        self.session.verify = SPLUNK_HEC_TLSVERIFY
        self.session.headers = SPLUNK_HEC_HEADERS
        self.session.logger = logger


# This tasks is retryable when using otel or local splunk this should be rare but
# may happen
@shared_task(
    bind=True,
    base=HECTask,
    default_retry_delay=5,
    max_retries=60,
    retry_backoff=True,
    retry_backoff_max=1,
    autoretry_for=[ConnectionError, ConnectTimeout, ReadTimeout, Timeout],
    retry_jitter=True,
)
def send(self, data):
    # If a device is very large a walk may produce more than 1MB of data.
    # 50 items is a reasonable guess to keep the post under the http post size limit
    # and be reasonable efficient
    for i in range(0, len(data), SPLUNK_HEC_CHUNK_SIZE):
        # using sessions is important this avoid expensive setup time
        try:
            response = self.session.post(
                SPLUNK_HEC_URI,
                data="\n".join(data[i : i + SPLUNK_HEC_CHUNK_SIZE]),
                timeout=60,
            )
        except ConnectionError:
            logger.error(f"Unable to communicate with Splunk endpoint")
            self.retry(countdown=30)
            raise
        # 200 is good
        if response.status_code == 200:
            logger.debug(f"Response code is {response.status_code} {response.text}")
            pass
        # These errors can't be retried
        elif response.status_code in (403, 401, 400):
            logger.error(
                f"Response code is {response.status_code} {response.text} headers were {SPLUNK_HEC_HEADERS}"
            )
        # These can be but are not exceptions so we will setup retry ourself
        elif response.status_code in (500, 503):
            logger.warn(f"Response code is {response.status_code} {response.text}")
            self.retry(countdown=5)
        # Any other response code is undocumented we have to treat this as fatal
        else:
            logger.error(f"Response code is {response.status_code} {response.text}")


def valueAsBest(value) -> Union[str, float]:
    try:
        return float(value)
    except:
        return value


@shared_task()
def prepare(work):
    splunk_input = []
    #     {
    #   "time": 1486683865,
    #   "event": "metric",
    #   "source": "metrics",
    #   "sourcetype": "perflog",
    #   "host": "host_1.splunk.com",
    #   "fields": {
    #     "service_version": "0",
    #     "service_environment": "test",
    #     "path": "/dev/sda1",
    #     "fstype": "ext3",
    #     "metric_name:cpu.usr": 11.12,
    #     "metric_name:cpu.sys": 12.23,
    #     "metric_name:cpu.idle": 13.34
    #   }
    # }
    if work.get("sourcetype") == "sc4snmp:traps":
        return prepare_trap_data(work)

    for key, data in work["result"].items():
        if len(data["metrics"].keys()) > 0:
            metric = {
                "time": work["time"],
                "event": "metric",
                "source": "sc4snmp",
                "sourcetype": "sc4snmp:metric",
                "host": work["address"],
                "index": SPLUNK_HEC_INDEX_METRICS,
                "fields": {},
            }
            if "frequency" in work:
                metric["fields"]["frequency"] = work["frequency"]
            if "profiles" in data:
                metric["fields"]["profiles"] = data["profiles"]
            for field, values in data["fields"].items():
                short_field = field.split(".")[-1]
                metric["fields"][short_field] = valueAsBest(values["value"])
            for field, values in data["metrics"].items():
                metric["fields"][f"metric_name:sc4snmp.{field}"] = valueAsBest(
                    values["value"]
                )
            splunk_input.append(json.dumps(metric, indent=None))
        else:
            event = {
                "time": work["time"],
                "event": json.dumps(data["fields"]),
                "source": "sc4snmp",
                "sourcetype": "sc4snmp:event",
                "host": work["address"],
                "index": SPLUNK_HEC_INDEX_EVENTS,
            }
            splunk_input.append(json.dumps(event, indent=None))

    return splunk_input


def prepare_trap_data(work):
    splunk_input = []
    for key, data in work["result"].items():
        processed = {}
        print(data["metrics"])
        if data["metrics"]:
            for k, v in data["metrics"].items():
                processed[k] = valueAsBest(v["value"])
        event = {
            "time": work["time"],
            "event": json.dumps(data["fields"] | processed),
            "source": "sc4snmp",
            "sourcetype": "sc4snmp:traps",
            "host": work["address"],
            "index": SPLUNK_HEC_INDEX_EVENTS,
        }
        splunk_input.append(json.dumps(event, indent=None))

    return splunk_input
