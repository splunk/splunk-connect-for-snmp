"""
Copyright 2018-2019 Splunk, Inc..

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import json
import logging
import os
import sys
import time

import requests
from exceptions_tests import UiTestsException
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

TIMEROUT = 500

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter(
    "%(asctime)s - %(name)s -" + " %(levelname)s - %(message)s"
)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_events_from_splunk(
    start_time="-1h@h",
    end_time="now",
    url="",
    user="",
    query="",
    password="",
):
    """
    send a search request to splunk and return the events from the result
    """
    logger.info(
        f"search query = {str(query)} ,start_time: {start_time}, end_time: {end_time}"
    )
    events = _collect_events(query, start_time, end_time, url, user, password)

    return events


def _collect_events(query, start_time, end_time, url="", user="", password=""):
    """
    Collect events by running the given search query
    @param: query (search query)
    @param: start_time (search start time)
    @param: end_time (search end time)
    returns events
    """

    search_url = "{}/services/search/jobs?output_mode=json".format(url)
    logger.debug("requesting: %s", search_url)
    data = {
        "search": query,
        "earliest_time": start_time,
        "latest_time": end_time,
    }
    logger.debug("SEARCH DATA: {}".format(data))
    create_job = _requests_retry_session().post(
        search_url, auth=(user, password), verify=False, data=data
    )
    _check_request_status(create_job)

    json_res = create_job.json()
    job_id = json_res["sid"]
    events = _wait_for_job_and_get_events(job_id, url, user, password)

    return events


def _collect_metrics(
    start_time, end_time, url="", user="", password="", index="", metric_name=""
):
    """
    Verify metrics by running the given api query
    @param: dimension (metric dimension)
    @param: metric_name (metric name)
    @param: start_time (search start time)
    @param: end_time (search end time)
    returns events
    """
    api_url = (
        url
        + "/services/catalog/metricstore/dimensions/host/values?filter=index%3d"
        + index
        + "&metric_name="
        + metric_name
        + "&earliest="
        + start_time
        + "&latest="
        + end_time
        + "&output_mode=json"
    )
    logger.debug("requesting: %s", api_url)

    create_job = _requests_retry_session().get(
        api_url, auth=(user, password), verify=False
    )

    _check_request_status(create_job)

    json_res = create_job.json()

    events = json_res["entry"]
    # logger.info('events: %s', events)

    return events


def _wait_for_job_and_get_events(job_id, url="", user="", password=""):
    """
    Wait for the search job to finish and collect the result events
    @param: job_id
    returns events
    """
    events = []
    job_url = "{}/services/search/jobs/{}?output_mode=json".format(url, str(job_id))
    logger.debug("requesting: %s", job_url)

    for _ in range(TIMEROUT):
        res = _requests_retry_session().get(
            job_url, auth=(user, password), verify=False
        )
        _check_request_status(res)

        job_res = res.json()
        dispatch_state = job_res["entry"][0]["content"]["dispatchState"]

        if dispatch_state == "DONE":
            events = _get_events(job_id, url, user, password)
            break
        if dispatch_state == "FAILED":
            raise UiTestsException("Search job: {} failed".format(job_url))
        time.sleep(1)

    return events


def _get_events(job_id, url="", user="", password=""):
    """
    collect the result events from a search job
    @param: job_id
    returns events
    """
    event_url = "{}/services/search/jobs/{}/events?output_mode=json".format(
        url, str(job_id)
    )
    logger.debug("requesting: %s", event_url)

    event_job = _requests_retry_session().get(
        event_url, auth=(user, password), verify=False
    )
    _check_request_status(event_job)

    event_job_json = event_job.json()
    events = event_job_json["results"]
    logger.debug("Events from get_events method returned %s events", len(events))

    return events


def _check_request_status(req_obj):
    """
    check if a request is successful
    @param: req_obj
    returns True/False
    """
    if not req_obj.ok:
        raise UiTestsException(
            "status code: {} \n details: {}".format(
                str(req_obj.status_code), req_obj.text
            )
        )


def _requests_retry_session(
    retries=10, backoff_factor=0.1, status_forcelist=(500, 502, 504)
):
    """
    create a retry session for HTTP/HTTPS requests
    @param: retries (num of retry time)
    @param: backoff_factor
    @param: status_forcelist (list of error status code to trigger retry)
    @param: session
    returns: session
    """
    session = requests.Session()
    retry = Retry(
        total=int(retries),
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session
