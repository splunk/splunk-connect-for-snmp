import json

try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass

import os

import requests
from celery import Task, shared_task
from celery.utils.log import get_task_logger

from splunk_connect_for_snmp.poller import app

OTEL_SERVER_METRICS_URL = os.getenv("OTEL_SERVER_METRICS_URL")
OTEL_SERVER_LOGS_URL = os.getenv("OTEL_SERVER_LOGS_URL")
SPLUNK_HEC_TOKEN = os.getenv("SPLUNK_HEC_TOKEN")
SPLUNK_HEC_INDEX_EVENTS = os.getenv("SPLUNK_HEC_INDEX_EVENTS", "netops")
SPLUNK_HEC_INDEX_METRICS = os.getenv("SPLUNK_HEC_INDEX_METRICS", "netmetrics")


logger = get_task_logger(__name__)


class HECTask(Task):
    def __init__(self):
        pass


@shared_task(bind=True, base=HECTask)
def send(self, metrics, events):
    for item in metrics:
        try:
            # response = requests.post(headers={'Authorization': f'Splunk {SPLUNK_HEC_TOKEN}'}, url=SPLUNK_HEC_URI_METRICS,
            #                          json=item, timeout=60, verify=False)
            response = requests.post(url=OTEL_SERVER_METRICS_URL, json=item, timeout=60, verify=False)
            logger.debug("Response code is %s", response.status_code)
            logger.debug("Response is %s", response.text)
        except requests.ConnectionError as e:
            logger.error(
                f"Connection error when sending data to HEC index - {metrics['index']}: {e}"
            )

    for item in events:
        try:
            response = requests.post(url=OTEL_SERVER_LOGS_URL, json=item, timeout=60, verify=False)
            logger.debug("Response code is %s", response.status_code)
            logger.debug("Response is %s", response.text)
        except requests.ConnectionError as e:
            logger.error(
                f"Connection error when sending data to HEC index - {events['index']}: {e}"
            )

    logger.debug(f"send result size {len(metrics)}")

    return "sent"


@shared_task(bind=True)
def prepare(self, target, ts, result):
    splunk_metrics = []
    splunk_events = []

    logger.debug(f"@@@@@@@@@@@@@ Timestamp = {ts}")

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
                metric["fields"][short_field] = values["value"]
            for field, values in data["metrics"].items():
                metric["fields"][f"metric_name:{field}"] = values["value"]
            splunk_metrics.append(metric)
        else:
            event = {
                "time": ts,
                "event": json.dumps(data["fields"]),
                "source": "sc4snmp",
                "sourcetype": "sc4snmp:event",
                "host": target,
                "index": SPLUNK_HEC_INDEX_EVENTS,
            }

            splunk_events.append(event)

    logger.info(f"Size of metrics: {len(splunk_metrics)}")
    logger.info(f"Size of events: {len(splunk_events)}")

    app.send_task(
        "splunk_connect_for_snmp.splunk.tasks.send",
        ([splunk_metrics, splunk_events]),
    )

    return splunk_metrics, splunk_events
