#   ########################################################################
#   Copyright 2021 Splunk Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
#   ########################################################################
import time


def splunk_single_search(service, search):
    kwargs_normal_search = {"exec_mode": "normal"}
    tried = 0
    while True:
        job = service.jobs.create(search, **kwargs_normal_search)
        while True:
            while not job.is_ready():
                pass
            stats = {
                "isDone": job["isDone"],
                "doneProgress": float(job["doneProgress"]) * 100,
                "scanCount": int(job["scanCount"]),
                "eventCount": int(job["eventCount"]),
                "resultCount": int(job["resultCount"]),
            }

            if stats["isDone"] == "1":
                break
            else:
                time.sleep(2)

        result_count = stats["resultCount"]
        event_count = stats["eventCount"]
        if result_count > 0 or tried > 5:
            break
        else:
            tried += 1
            time.sleep(5)
    return result_count, event_count
