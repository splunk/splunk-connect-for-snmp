import csv
import io
import json
import logging
import os
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest
import yaml

from integration_tests.utils.compose import compose_environment
from integration_tests.utils.deployment import (
    APP_PYTHON,
    DOCKER,
    _run_integration_command,
    application_context,
    close_observer,
    helm_command,
    probe_application,
    probe_program,
    restart_sc4snmp_component,
)
from integration_tests.utils.files import (
    read_private_json,
    write_container_file,
    write_private,
)
from integration_tests.utils.splunk_test_utils import upgrade_env_compose

logger = logging.getLogger(__name__)

CSV_FIELDS = (
    "address,port,version,community,secret,security_engine,walk_interval,"
    "profiles,smart_profiles,delete"
).split(",")


def wait_for(predicate, description, timeout, interval=0.5):
    logger.debug(f"Waiting for an integration condition with timeout={timeout}s")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            logger.debug("Integration condition satisfied")
            return result
        time.sleep(min(interval, max(0, deadline - time.monotonic())))
    logger.warning(f"Integration condition timed out after {timeout}s")
    pytest.fail(f"Timed out waiting for {description}", pytrace=False)


class LiveJitter:
    def __init__(self, target, manifest, directory, timeout):
        self.target = target
        self.devices = sorted(
            manifest["devices"], key=lambda device: int(device["label"][2:])
        )
        self.directory = Path(directory)
        self.timeout = timeout
        self.mode = target["mode"]
        self.started_at = time.time()
        self.observations = []
        self.stop_observer = threading.Event()
        self.observer = None
        self.observer_process = None
        self.observer_gaps = []
        self.changed = False
        self.events = []
        self.event_process = None
        self.event_reader = None
        self.event_ready = threading.Event()
        self.credentials = read_private_json(manifest["credentials_file"])
        assert target.get("isolated") is True, "An isolated test target is required"
        assert target["run_id"] == manifest["run_id"], "Fixture run IDs differ"
        assert self.mode == manifest["mode"], "Fixture deployment modes differ"
        count = len(self.devices)
        assert count == 5, "The jitter suite uses five functional devices"
        assert len({(d["address"], d["port"]) for d in self.devices}) == count
        assert {d["label"] for d in self.devices} == {
            f"IP{i}" for i in range(1, count + 1)
        }
        assert {d["version"] for d in self.devices} == {"2c", "3"}
        self.context = application_context(target, self.run)
        self.component_uids = self.context["component_uids"]
        self.images = self.context["images"]
        if self.mode == "microk8s":
            self.kube = self.context["kube"]
            self.selector = self.context["selector"]
        else:
            assert self.mode == "docker-compose", "Unsupported jitter deployment mode"
            self.compose = self.context["compose"]
        assert (
            len(set(self.images.values())) == 1
        ), "Test components must use the same image"
        baseline = self.probe("state")
        assert baseline["foreign_entries"] == 0, "Unexpected device in isolated target"
        assert not baseline["entries"], "Use an empty isolated target for this test"
        assert baseline[
            "drained"
        ], "The isolated target must start without outstanding work"
        logger.info(
            f"Isolated polling target ready: backend={self.mode} "
            f"devices={len(self.devices)}"
        )

    def command_environment(self):
        if self.mode == "docker-compose":
            return compose_environment(self.target)
        return None

    def run(self, arguments, content=None, timeout=None):
        return _run_integration_command(
            arguments,
            "Polling test command",
            timeout=timeout or self.timeout,
            content=content,
            env=self.command_environment(),
            error_file=self.directory / f"command-failure-{uuid4().hex}.txt",
        )

    def kube_json(self, *arguments):
        return json.loads(self.run([*self.kube, *arguments, "-o", "json"]) or "null")

    def component(self, name):
        resource = self.context["deployments"][name]
        metadata = self.kube_json("get", "deployment", resource)["metadata"]
        assert metadata["uid"] == self.component_uids[name]
        return resource

    def exec_prefix(self, component="worker-poller"):
        if self.mode == "microk8s":
            self.component(component)
        return self.context["exec_prefixes"][component]

    def probe(self, action="snapshot", *, component=None, **data):
        if component is None:
            # A probe imports the app. Keep that extra process off busy workers.
            component = (
                "scheduler" if self.mode == "docker-compose" else "worker-poller"
            )
        # Recheck Kubernetes ownership before using the saved exec command.
        self.exec_prefix(component)
        return probe_application(
            self.context, self.devices, action, self.run, component=component, **data
        )

    def open_observer(self, action):
        request = {
            "devices": self.devices,
            "action": action,
            "duration": max(3600, self.timeout * 8),
        }
        name = "event" if action == "events" else "schedule"
        errors = (self.directory / f"{name}-observer-errors.txt").open("a")
        os.chmod(errors.name, 0o600)
        prefix = self.context.get("observer_prefix")
        if prefix is None:
            prefix = self.exec_prefix("worker-sender")
        process = subprocess.Popen(
            [
                *prefix,
                APP_PYTHON,
                "-u",
                "-c",
                "import json, sys\nexec(json.loads(sys.stdin.readline()))",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=errors,
            text=True,
            env=self.command_environment(),
        )
        errors.close()
        # Keep stdin open so cleanup can send the remote observer a stop line.
        process.stdin.write(json.dumps(probe_program(request)) + "\n")
        process.stdin.flush()
        return process

    def start_events(self):
        if self.event_process and self.event_process.poll() is None:
            return
        logger.info("Starting the Celery event observer")
        self.event_ready.clear()
        self.event_process = self.open_observer("events")
        process = self.event_process

        def receive():
            for line in process.stdout:
                if line.strip() == "JITTER_EVENT_READY":
                    self.event_ready.set()
                elif line.startswith("JITTER_EVENT="):
                    self.events.append(json.loads(line.removeprefix("JITTER_EVENT=")))

        self.event_reader = threading.Thread(target=receive, daemon=True)
        self.event_reader.start()
        wait_for(self.event_ready.is_set, "the Celery event observer subscription", 30)
        logger.info("Celery event observer ready")

    def stop_events(self):
        close_observer(self.event_process)
        if self.event_reader:
            self.event_reader.join(timeout=5)
        write_private(self.directory / "task-events.json", json.dumps(self.events))
        logger.info(f"Celery event observer stopped: events={len(self.events)}")

    def snapshot(self):
        if self.observer and not self.stop_observer.is_set():
            requested_at = time.time()
            snapshot = wait_for(
                lambda: (
                    current
                    if self.observations
                    and (current := self.observations[-1])["observed_at"]
                    >= requested_at
                    else None
                ),
                "a fresh Redis schedule observation",
                self.timeout,
                interval=0.05,
            )
        else:
            snapshot = self.probe()
        assert snapshot["foreign_entries"] == 0, "Unexpected device in isolated target"
        return snapshot

    def drained(self):
        state = self.probe("drained")
        write_private(self.directory / "drain-state.json", json.dumps(state))
        logger.debug(
            f"Published-work accounting: workers={state['workers']} "
            f"complete={state['worker_replies_complete']} queued={state['queued']} "
            f"unacked={state['unacked']} unacked_index={state['unacked_index']}"
        )
        return state["drained"]

    def start_observing(self):
        logger.info("Starting the Redis schedule observer")
        self.stop_observer.clear()

        def observe():
            while not self.stop_observer.is_set():
                process = None
                error_type = None
                try:
                    process = self.open_observer("observe")
                    self.observer_process = process
                    for line in process.stdout:
                        if self.stop_observer.is_set():
                            break
                        if line.startswith("JITTER_SNAPSHOT="):
                            snapshot = json.loads(line.removeprefix("JITTER_SNAPSHOT="))
                            if snapshot["foreign_entries"]:
                                raise RuntimeError(
                                    "Unexpected device in isolated target"
                                )
                            self.observations.append(snapshot)
                        elif line.startswith("JITTER_SNAPSHOT_GAP="):
                            self.observer_gaps.append(
                                json.loads(line.removeprefix("JITTER_SNAPSHOT_GAP="))
                            )
                except (
                    OSError,
                    RuntimeError,
                    ValueError,
                    subprocess.SubprocessError,
                ) as error:
                    error_type = type(error).__name__
                finally:
                    close_observer(process)
                    self.observer_process = None
                if error_type or not self.stop_observer.is_set():
                    # Reconnect after a sender rollout, but retain the missing interval.
                    error_type = error_type or "ObserverDisconnected"
                    self.observer_gaps.append(
                        {"observed_at": time.time(), "error": error_type}
                    )
                if not self.stop_observer.is_set():
                    logger.warning(
                        f"Schedule observer reconnecting: error_type={error_type}"
                    )
                self.stop_observer.wait(0.2)

        self.observer = threading.Thread(target=observe, daemon=True)
        self.observer.start()
        wait_for(lambda: self.observations, "the first Redis schedule observation", 30)
        logger.info("Redis schedule observer ready")

    def stop_observing(self):
        self.stop_observer.set()
        close_observer(self.observer_process)
        if self.observer:
            self.observer.join(timeout=15)
            if self.observer.is_alive():
                logger.error("Redis schedule observer did not stop")
                raise RuntimeError("The Redis schedule observer did not stop")
        write_private(
            self.directory / "observations.json", json.dumps(self.observations)
        )
        write_private(
            self.directory / "observation-gaps.json",
            json.dumps(
                {
                    "interrupted": bool(self.observer_gaps),
                    "gaps": self.observer_gaps,
                }
            ),
        )
        logger.info(
            f"Redis schedule observer stopped: snapshots={len(self.observations)} "
            f"gaps={len(self.observer_gaps)}"
        )

    def inventory(self, profiles="jitter_short", interval=1800, **overrides):
        rows = []
        for device in self.devices:
            credentials = self.credentials[device["credential_ref"]]
            row = {
                "address": device["address"],
                "port": device["port"],
                "version": device["version"],
                "walk_interval": interval,
                "profiles": profiles,
                "smart_profiles": "false",
                "delete": "false",
                "community": credentials.get("community", ""),
                "secret": (
                    self.target.get("v3_secret", "") if device["version"] == "3" else ""
                ),
                "security_engine": credentials.get("security_engine_id", ""),
            }
            if device["version"] == "3":
                assert row[
                    "secret"
                ], "Configure the fixture's mounted SNMPv3 secret reference"
            row.update(overrides)
            rows.append(row)
        return rows

    def configure(
        self,
        profiles,
        rows,
        *,
        enabled=False,
        window=60,
        groups=None,
        poll_base=False,
        full_walk=False,
        from_mongo=False,
    ):
        if from_mongo and self.mode == "microk8s":
            values = yaml.safe_load(Path(self.target["values_file"]).read_text())
            ui = values.get("UI", {})
            auth = ui.get("auth", {})
            if not (
                auth.get("enabled")
                and auth.get("existingSecret")
                and ui.get("valuesFileDirectory")
            ):
                raise RuntimeError(
                    "Mongo inventory requires approved authenticated UI values "
                    "in the supplied target"
                )
        logger.info(
            f"Applying polling configuration: backend={self.mode} rows={len(rows)} "
            f"profiles={len(profiles)} enabled={enabled} window_seconds={window} "
            f"mongo_source={from_mongo}"
        )
        # Keep shipped mandatory/base frequencies out of this controlled cohort.
        profiles = {
            name: {"enabled": False}
            for name in ("BaseUpTime", "BaseDeviceData", "EnrichIF", "BaseIF")
        } | profiles
        config = {"profiles": profiles, "groups": groups or {}}
        settings = {"enabled": enabled, "windowSeconds": window}
        # A fresh registration must not overlap a previous Beat policy during
        # rollout. Activate settings on the empty target before adding devices.
        inventories = (
            ([], rows)
            if self.mode == "microk8s" and not self.changed and rows
            else (rows,)
        )
        self.changed = True
        self.start_events()
        for inventory_rows in inventories:
            logger.debug(f"Applying inventory phase: rows={len(inventory_rows)}")
            started = time.time()
            stream = io.StringIO()
            writer = csv.DictWriter(stream, CSV_FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(inventory_rows)
            if from_mongo:
                self.probe("configure_mongo", rows=inventory_rows, config=config)
            if self.mode == "microk8s":
                override = self.directory / "values-jitter.yaml"
                write_private(
                    override,
                    yaml.safe_dump(
                        {
                            "scheduler": {
                                "pollingJitter": settings,
                                "profiles": yaml.safe_dump(profiles),
                                "groups": yaml.safe_dump(groups or {}),
                            },
                            "poller": {
                                "inventory": stream.getvalue(),
                                "pollBaseProfiles": poll_base,
                                "enableFullWalk": full_walk,
                            },
                            "UI": {"enable": from_mongo},
                        }
                    ),
                )
                values_files = (self.target["values_file"], override)
                self.inventory_template = yaml.safe_load(
                    self.run(
                        [
                            *helm_command(self.target, "template", *values_files),
                            "--show-only",
                            "templates/inventory/job.yaml",
                        ]
                    )
                )
                container = self.inventory_template["spec"]["template"]["spec"][
                    "containers"
                ][0]
                assert (
                    container["image"] == self.images["worker-poller"]
                ), "Rendered inventory Job must use the tested application image"
                job_name = self.inventory_template["metadata"]["name"]
                delete_job = [
                    *self.kube,
                    "delete",
                    "job",
                    job_name,
                    "--ignore-not-found=true",
                    "--wait=false",
                ]
                current = self.kube_json("get", "job", job_name, "--ignore-not-found")
                if current:
                    assert (
                        current["metadata"]
                        .get("annotations", {})
                        .get("meta.helm.sh/release-name")
                        == self.target["release"]
                    ), "The inventory Job is not owned by this release"
                    assert any(
                        condition["type"] == "Complete"
                        and condition["status"] == "True"
                        for condition in current.get("status", {}).get("conditions", [])
                    ), "Wait for the existing inventory writer before reloading"
                    self.run(delete_job)
                # Follow the existing integration flow. Recreate the completed Job,
                # then apply actual chart values so the normal loader runs on upgrade.
                self.run(
                    [
                        *helm_command(self.target, "upgrade", *values_files),
                        "--wait",
                        "--wait-for-jobs",
                        f"--timeout={self.timeout}s",
                    ],
                    timeout=self.timeout + 30,
                )
                self.run(delete_job)
                self.context = application_context(self.target, self.run)
                if not inventory_rows and rows:
                    # Helm can report the new workers ready while old workers
                    # still consume tasks. Let them exit before adding devices.
                    terminating = [
                        pod["metadata"]["name"]
                        for pod in self.kube_json("get", "pods", "-l", self.selector)[
                            "items"
                        ]
                        if pod["metadata"].get("deletionTimestamp")
                    ]
                    if terminating:
                        logger.info("Waiting for previous workers to exit")
                        self.run(
                            [
                                *self.kube,
                                "wait",
                                "--for=delete",
                                *(f"pod/{name}" for name in terminating),
                                f"--timeout={self.timeout}s",
                            ]
                        )
                    wait_for(
                        self.drained,
                        "idle replacement workers before initial registration",
                        self.timeout,
                    )
            else:
                write_container_file(self.target["config_file"], yaml.safe_dump(config))
                write_container_file(self.target["inventory_file"], stream.getvalue())
                environment = {
                    "POLLING_JITTER_ENABLED": str(enabled).lower(),
                    "POLLING_JITTER_WINDOW_SECONDS": str(window),
                    "POLL_BASE_PROFILES": str(poll_base).lower(),
                    "ENABLE_FULL_WALK": str(full_walk).lower(),
                    "CONFIG_FROM_MONGO": str(from_mongo).lower(),
                }
                for name, value in environment.items():
                    upgrade_env_compose(name, value, self.target["env_file"])
                self.run([*self.compose, "up", "-d", "scheduler", "worker-poller"])
                self.load_inventory()
        logger.info("Polling configuration and inventory applied")
        return started, time.time()

    def load_inventory(self, concurrent=1):
        logger.info(
            f"Starting explicit inventory reload: backend={self.mode} "
            f"concurrent_jobs={concurrent}"
        )
        started = time.time()
        self.start_events()

        def load(_):
            if self.mode == "microk8s":
                document = deepcopy(self.inventory_template)
                name = f"jitter-inventory-{uuid4().hex[:12]}"
                document["metadata"] = {
                    "name": name,
                    "namespace": self.target["namespace"],
                    "labels": {"sc4snmp.integration.jitter-run": self.target["run_id"]},
                }
                self.run([*self.kube, "create", "-f", "-"], json.dumps(document))
                self.run(
                    [
                        *self.kube,
                        "wait",
                        "--for=condition=Complete",
                        f"job/{name}",
                        f"--timeout={self.timeout}s",
                    ]
                )
                self.run(
                    [
                        *self.kube,
                        "delete",
                        "job",
                        name,
                        "--ignore-not-found=true",
                        "--wait=false",
                    ]
                )
            else:
                self.run([*self.compose, "run", "--rm", "--no-deps", "inventory"])

        with ThreadPoolExecutor(max_workers=concurrent) as executor:
            list(executor.map(load, range(concurrent)))
        logger.info("Explicit inventory reload completed")
        return started, time.time()

    def wait_entries(self, count):
        return wait_for(
            lambda: (
                snapshot
                if len((snapshot := self.snapshot())["entries"]) == count
                else None
            ),
            f"{count} expected schedules",
            self.timeout,
        )

    def wait_count(self, key, count):
        return wait_for(
            lambda: (
                snapshot
                if (snapshot := self.snapshot())["entries"]
                .get(key, {})
                .get("count", -1)
                >= count
                else None
            ),
            "the next Beat reservation",
            self.timeout,
        )

    def restart(self, component):
        assert component in ("scheduler", "worker-poller", "worker-sender")
        logger.info(f"Restarting polling component: component={component}")
        if component == "worker-sender":
            self.stop_events()
        restart_sc4snmp_component(
            self.mode,
            compose_service=component,
            kubernetes_resource=(
                f"deployment/{self.component(component)}"
                if self.mode == "microk8s"
                else ""
            ),
            namespace=self.target.get("namespace", "sc4snmp"),
            timeout=self.timeout,
            kubectl=self.kube[:-2] if self.mode == "microk8s" else None,
            compose_file=self.target.get("compose_file"),
            env_file=self.target.get("env_file"),
            project=self.target.get("project"),
            docker=DOCKER,
            env=self.command_environment(),
            error_file=self.directory / f"restart-failure-{uuid4().hex}.txt",
            restart_only=True,
        )
        logger.info(f"Polling component restarted: component={component}")


def short_profiles():
    return {
        "jitter_short": {
            "frequency": 10,
            "varBinds": [["SNMPv2-MIB", "sysUpTime", 0], ["SNMPv2-MIB", "sysName", 0]],
        },
    }
