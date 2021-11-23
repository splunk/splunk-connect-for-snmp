try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass

import json
import os
from typing import Union

from celery import Task, shared_task
from celery.utils.log import get_task_logger
from requests import ConnectionError, ConnectTimeout, ReadTimeout, Session, Timeout

from splunk_connect_for_snmp.common.hummanbool import hummanBool

SPLUNK_HEC_URI = os.getenv("SPLUNK_HEC_URI")
SPLUNK_HEC_TOKEN = os.getenv("SPLUNK_HEC_TOKEN", None)
SPLUNK_HEC_INDEX_EVENTS = os.getenv("SPLUNK_HEC_INDEX_EVENTS", "netops")
SPLUNK_HEC_INDEX_METRICS = os.getenv("SPLUNK_HEC_INDEX_METRICS", "netmetrics")
SPLUNK_HEC_TLSVERIFY = hummanBool(
    os.getenv("SPLUNK_HEC_TLSVERIFY", "yes"), default=True
)

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
        response = self.session.post(
            SPLUNK_HEC_URI,
            data="\n".join(data[i : i + SPLUNK_HEC_CHUNK_SIZE]),
            timeout=60,
        )
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
    for key, data in work["result"].items():
        if len(data["metrics"].keys()) > 0:
            metric = {
                "time": work["ts"],
                "event": "metric",
                "source": "sc4snmp",
                "sourcetype": work.get("sourcetype", "sc4snmp:metric"),
                "host": work["host"],
                "index": SPLUNK_HEC_INDEX_METRICS,
                "fields": {},
            }
            for field, values in data["fields"].items():
                short_field = field.split(".")[-1]
                metric["fields"][short_field] = valueAsBest(values["value"])
            for field, values in data["metrics"].items():
                metric["fields"][f"metric_name:{field}"] = valueAsBest(values["value"])
            splunk_input.append(json.dumps(metric, indent=None))
        else:
            event = {
                "time": work["ts"],
                "event": json.dumps(data["fields"]),
                "source": "sc4snmp",
                "sourcetype": work.get("sourcetype", "sc4snmp:event"),
                "host": work["host"],
                "index": SPLUNK_HEC_INDEX_EVENTS,
            }
            splunk_input.append(json.dumps(event, indent=None))

    return splunk_input
