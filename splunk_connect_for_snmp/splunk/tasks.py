try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass

import json
import os

import requests
from celery import Task, shared_task
from celery.utils.log import get_task_logger

from splunk_connect_for_snmp.poller import app

SPLUNK_HEC_URI = os.getenv("SPLUNK_HEC_URI")
SPLUNK_HEC_TOKEN = os.getenv("SPLUNK_HEC_TOKEN")
SPLUNK_HEC_INDEX_EVENTS = os.getenv("SPLUNK_HEC_INDEX_EVENTS", "netops")
SPLUNK_HEC_INDEX_METRICS = os.getenv("SPLUNK_HEC_INDEX_METRICS", "netmetrics")


logger = get_task_logger(__name__)


class HECTask(Task):
    def __init__(self):
        pass


@shared_task(bind=True, base=HECTask)
def send(self, result):
    logger.debug("+++++++++endpoint+++++++++ %s", SPLUNK_HEC_URI)

    for item in result:
        try:
            response = requests.post(url=SPLUNK_HEC_URI, json=item, timeout=60, verify=False)
            logger.debug("Response code is %s", response.status_code)
            logger.debug("Response is %s", response.text)
        except requests.ConnectionError as e:
            logger.error(
                f"Connection error when sending data to HEC index - {result['index']}: {e}"
            )

    logger.debug(f"send result size {len(result)}")

    return "sent"


@shared_task(bind=True)
def prepare(self, target, ts, result):
    splunk_metrics = []
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
    for key, data in result.items():
        if len(data["metrics"]) > 0:
            metric = {
                "time": ts,
                "event": "metric",
                "source": "sc4snmp",
                "sourcetype": "sc4snmp:metric",
                "host": target,
                "index": SPLUNK_HEC_INDEX_METRICS,
                "fields": {},
            }
            for field, values in data["fields"].items():
                short_field = field.split(".")[-1]
                metric['fields'][short_field] = values["value"]
            for field, values in data["metrics"].items():
                metric['fields'][f"metric_name:{field}"] = values["value"]
            splunk_metrics.append(metric)

    app.send_task(
        "splunk_connect_for_snmp.splunk.tasks.send",
        ([splunk_metrics]),
    )

    return splunk_metrics
