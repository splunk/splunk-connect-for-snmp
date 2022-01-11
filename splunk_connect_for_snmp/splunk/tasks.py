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
from splunk_connect_for_snmp.common.custom_translations import load_custom_translations

try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass

import json
import os
from typing import Union
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

OTEL_METRICS_URL = os.getenv("OTEL_METRICS_URL", None)

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


class PrepareTask(Task):
    def __init__(self):
        self.custom_translations = load_custom_translations()


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
    if SPLUNK_HEC_TOKEN:
        do_send(data["events"], SPLUNK_HEC_URI, self)
        do_send(data["metrics"], SPLUNK_HEC_URI, self)
    if OTEL_METRICS_URL:
        do_send(data["metrics"], OTEL_METRICS_URL, self)


def do_send(data, destination_url, self):
    # If a device is very large a walk may produce more than 1MB of data.
    # 50 items is a reasonable guess to keep the post under the http post size limit
    # and be reasonable efficient
    for i in range(0, len(data), SPLUNK_HEC_CHUNK_SIZE):
        # using sessions is important this avoid expensive setup time
        try:
            response = self.session.post(
                destination_url,
                data="\n".join(data[i: i + SPLUNK_HEC_CHUNK_SIZE]),
                timeout=60,
            )
        except ConnectionError:
            logger.warning(f"Unable to communicate with {destination_url} endpoint")
            self.retry(countdown=30)
            raise
        # 200 is good
        if response.status_code in (200, 202):
            logger.debug(f"Response code is {response.status_code} {response.text}")
            pass
        # These errors can't be retried
        elif response.status_code in (403, 401, 400):
            logger.error(
                f"Response code is {response.status_code} {response.text} headers were {SPLUNK_HEC_HEADERS}"
            )
        # These can be but are not exceptions so we will setup retry ourself
        elif response.status_code in (500, 503):
            logger.warning(f"Response code is {response.status_code} {response.text}")
            self.retry(countdown=5)
        # Any other response code is undocumented we have to treat this as fatal
        else:
            logger.error(f"Response code is {response.status_code} {response.text}")


def valueAsBest(value) -> Union[str, float]:
    try:
        return float(value)
    except:
        return value


@shared_task(
    bind=True,
    base=PrepareTask
)
def prepare(self, work):
    events = []
    metrics = []

    if work.get("sourcetype") == "sc4snmp:traps":
        return {"events": prepare_trap_data(apply_custom_translations(work, self.custom_translations)), "metrics": metrics}

    work = apply_custom_translations(work, self.custom_translations)

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
            metrics.append(json.dumps(metric, indent=None))
        else:
            event = {
                "time": work["time"],
                "event": json.dumps(data["fields"]),
                "source": "sc4snmp",
                "sourcetype": "sc4snmp:event",
                "host": work["address"],
                "index": SPLUNK_HEC_INDEX_EVENTS,
            }
            events.append(json.dumps(event, indent=None))

    return {"metrics": metrics, "events": events}


def prepare_trap_data(work):
    events = []
    for key, data in work["result"].items():
        processed = {}
        if data["metrics"]:
            for k, v in data["metrics"].items():
                processed[k] = v
                processed[k]["value"] = valueAsBest(v["value"])
        event = {
            "time": work["time"],
            "event": json.dumps(data["fields"] | processed),
            "source": "sc4snmp",
            "sourcetype": "sc4snmp:traps",
            "host": work["address"],
            "index": SPLUNK_HEC_INDEX_EVENTS,
        }
        events.append(json.dumps(event, indent=None))

    return events


def apply_custom_translations(work, custom_translations):
    if custom_translations:
        for key, data in work["result"].items():
            apply_custom_translation_to_collection(custom_translations, data, "fields")
            apply_custom_translation_to_collection(custom_translations, data, "metrics")
    return work


def apply_custom_translation_to_collection(custom_translations, data, key):
    new_data = {}
    for field, values in data[key].items():
        mib, name = field.split(".")
        ct = custom_translations.get(mib, {}).get(name, None)
        if ct:
            if key == "fields":
                values["name"] = f"{mib}.{ct}"
            new_data[f"{mib}.{ct}"] = values
        else:
            new_data[field] = values
    data[key] = new_data
