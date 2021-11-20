try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass

import os

import requests
from celery import Task, shared_task
from celery.utils.log import get_task_logger

from splunk_connect_for_snmp.common.boolish import isFalseish, isTrueish
from splunk_connect_for_snmp.poller import app

SPLUNK_HEC_URI = os.getenv("SPLUNK_HEC_URI")
SPLUNK_HEC_TOKEN = os.getenv("SPLUNK_HEC_TOKEN")
SPLUNK_HEC_INDEX_EVENTS = os.getenv("SPLUNK_HEC_INDEX_EVENTS", "netops")
SPLUNK_HEC_INDEX_METRICS = os.getenv("SPLUNK_HEC_INDEX_METRICS", "netmetrics")


logger = get_task_logger(__name__)


class HECTask(Task):
    def __init__(self):
        self.verify = isFalseish(os.getenv("SPLUNK_HEC_TLSVERIFY", "yes"))
        self.session = requests.session()
        self.header = None


@shared_task(bind=True, base=HECTask)
def send(self, result):
    for item in result:
        try:
            response = self.session.post(
                url=SPLUNK_HEC_URI, json=item, timeout=60, verify=self.verify
            )
            logger.debug(f"Response code is {response.status_code} {response.text}")
        except requests.ConnectionError as e:
            logger.error(
                f"Connection error when sending data to HEC index - {result['index']}: {e}"
            )


@shared_task(bind=True)
def prepare(self, work):
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
    for key, data in work["result"].items():
        if len(data["metrics"]) > 0:
            metric = {
                "time": work["ts"],
                "event": "metric",
                "source": "sc4snmp",
                "sourcetype": "sc4snmp:metric",
                "host": work["host"],
                "index": SPLUNK_HEC_INDEX_METRICS,
                "fields": {},
            }
            for field, values in data["fields"].items():
                short_field = field.split(".")[-1]
                metric["fields"][short_field] = values["value"]
            for field, values in data["metrics"].items():
                metric["fields"][f"metric_name:{field}"] = values["value"]
            splunk_metrics.append(metric)

    return splunk_metrics
