import json
import logging
import secrets
import subprocess
import time
from functools import partial
from pathlib import Path

import yaml

from integration_tests.utils import simulators
from integration_tests.utils.compose import (
    compose_environment,
    prepare_compose,
    run_compose,
    start_compose,
)
from integration_tests.utils.deployment import (
    BASE_DIR,
    MICROK8S,
    _run_integration_command,
    application_context,
    helm_command,
    probe_application,
)
from integration_tests.utils.files import read_private_json, write_private

logger = logging.getLogger(__name__)
ROOT = BASE_DIR.parent


def run(directory, arguments, content=None, timeout=600, env=None):
    return _run_integration_command(
        arguments,
        "Application setup command",
        content=content,
        timeout=timeout,
        env=env,
        error_file=directory / "setup-failure.txt",
    )


def observe_target(directory, target, manifest, action):
    env = compose_environment(target) if target["mode"] == "docker-compose" else None
    execute = partial(run, directory, timeout=45, env=env)
    context = application_context(target, execute)
    target["component_uids"] = context["component_uids"]
    return probe_application(
        context, manifest["devices"], action, execute, component="worker-sender"
    )


def wait_for_application(directory, target, manifest):
    logger.info(f"Waiting for an empty isolated application: backend={target['mode']}")
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        try:
            snapshot = observe_target(directory, target, manifest, "state")
            if snapshot["drained"]:
                if snapshot["entries"] or snapshot["foreign_entries"]:
                    raise RuntimeError("The isolated application did not start empty")
                logger.info("The isolated application is ready with no pending work")
                return
        except (RuntimeError, subprocess.TimeoutExpired):
            pass
        time.sleep(1)
    logger.warning("Application readiness timed out. Owned state is retained")
    raise RuntimeError("The isolated application did not become ready and empty")


def prepare_kubernetes(directory, target, splunk, manifest, image):
    namespace_name = target["namespace"]
    kube = [*MICROK8S, "kubectl", "-n", namespace_name]
    helm = [*MICROK8S, "helm3", "-n", namespace_name]
    execute = partial(run, directory)
    release = manifest["run_id"]
    secret_name = f"{release}-snmpv3"
    hec_secret = f"{release}-hec"
    target.update(
        {
            "run_id": release,
            "release": release,
            "v3_secret": secret_name,
            "hec_secret": hec_secret,
            "values_file": str(directory / "effective-values.yaml"),
            "chart": str(ROOT / "charts/splunk-connect-for-snmp"),
        }
    )
    write_private(directory / "target.json", json.dumps(target))
    namespace = execute(
        [*kube, "get", "namespace", namespace_name, "--ignore-not-found", "-o", "name"],
    )
    if not namespace.strip():
        execute([*MICROK8S, "kubectl", "create", "namespace", namespace_name])
    credentials = read_private_json(manifest["credentials_file"])["v3"]
    hec = splunk["hec"]
    for field, data in {
        "v3_secret": {
            "userName": credentials["username"],
            "authKey": credentials["auth_key"],
            "authProtocol": "SHA",
            "privKey": credentials["priv_key"],
            "privProtocol": "AES",
            "securityEngineId": credentials["security_engine_id"],
        },
        "hec_secret": {"hec_token": hec["token"]},
    }.items():
        secret = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": target[field],
                "namespace": namespace_name,
                "labels": {"sc4snmp.integration.jitter-run": release},
            },
            "stringData": data,
        }
        created = json.loads(
            execute(
                [*kube, "create", "-f", "-", "-o", "json"],
                json.dumps(secret),
            )
        )
        target[f"{field}_uid"] = created["metadata"]["uid"]
        write_private(directory / "target.json", json.dumps(target))
    repository, separator, tag = image.rpartition(":")
    if not separator or "/" in tag:
        repository, tag = image, "latest"
    overrides = {
        "image": {"repository": repository, "tag": tag, "pullPolicy": "Never"},
        "splunk": {
            "enabled": True,
            "host": hec["host"],
            "port": str(hec.get("port", 8088)),
            "protocol": hec.get("scheme", "https"),
            "token": "",
            "tokenSecretRef": {"name": hec_secret, "key": "hec_token"},
            "insecureSSL": str(not hec.get("verify", True)).lower(),
            "eventIndex": target["event_index"],
            "metricsIndex": target["metric_index"],
        },
        # Only the owned devices are added later by the normal loader.
        "poller": {"usernameSecrets": [secret_name]},
        "redis": {"auth": {"enabled": True, "password": secrets.token_urlsafe(24)}},
        "mongodb": {"auth": {"rootPassword": secrets.token_urlsafe(24)}},
    }
    overrides_file = directory / "runtime-values.yaml"
    write_private(overrides_file, yaml.safe_dump(overrides))
    target["stage"] = "application"
    write_private(directory / "target.json", json.dumps(target))
    execute(
        [
            *helm_command(
                target,
                "install",
                ROOT / "integration_tests/jitter/values.yaml",
                overrides_file,
            ),
            "--wait",
            "--wait-for-jobs",
            "--timeout=10m",
        ],
        timeout=660,
    )
    execute(
        [
            *kube,
            "delete",
            "job",
            "-l",
            f"app.kubernetes.io/instance={release},app.kubernetes.io/component=inventory",
            "--ignore-not-found=true",
            "--wait=false",
        ]
    )
    effective = execute([*helm, "get", "values", release, "--all", "-o", "yaml"])
    write_private(target["values_file"], effective)
    settings = yaml.safe_load(effective)
    target["ha"] = (
        settings["redis"]["architecture"] == "replication"
        and settings["mongodb"]["mode"] == "replication"
    )


def prepare(mode, directory, splunk, image="snmp-local:latest"):
    if not splunk.get("hec", {}).get("token"):
        raise RuntimeError("Prepare the existing integration Splunk HEC token first")
    directory = Path(directory).resolve()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    if (directory / "target.json").exists() or (directory / "simulators").exists():
        raise RuntimeError("Use a new jitter run directory")
    logger.info(f"Preparing an isolated polling environment: backend={mode}")
    manifest = simulators.load_simulators(directory / "simulators", mode)
    target = {
        "mode": mode,
        "isolated": True,
        "stage": "infrastructure",
        "run_id": manifest["run_id"],
        "namespace": "sc4snmp",
        "manifest_file": str(directory / "simulators/endpoints.json"),
        "event_index": splunk.get("event_index", "netops"),
        "metric_index": splunk.get("metric_index", "netmetrics"),
    }
    if mode == "docker-compose":
        project = manifest["run_id"]
        target.update(
            {
                "project": project,
                "compose_file": str(directory / "docker-compose.yaml"),
                "env_file": str(directory / ".env"),
            }
        )
    write_private(directory / "target.json", json.dumps(target))
    if mode == "docker-compose":
        target.update(prepare_compose(directory, project, image, splunk))
        target["stage"] = "application"
        write_private(directory / "target.json", json.dumps(target))
        start_compose(target, read_private_json(manifest["credentials_file"]))
    else:
        prepare_kubernetes(directory, target, splunk, manifest, image)
    wait_for_application(directory, target, manifest)
    target["stage"] = "ready"
    write_private(directory / "target.json", json.dumps(target))
    logger.info(
        f"Isolated polling environment prepared: backend={mode}, "
        f"devices={len(manifest['devices'])}"
    )


def cleanup(target_file):
    target_file = Path(target_file).resolve()
    target = read_private_json(target_file)
    directory = target_file.parent
    execute = partial(run, directory)
    if target.get("isolated") is not True:
        logger.warning("Cleanup refused because target isolation is not confirmed")
        raise RuntimeError("The target is not an isolated fixture")
    if target.get("cleaned"):
        logger.info("The owned fixture was already cleaned. Storage remains retained")
        return
    logger.info(f"Starting isolated environment cleanup: backend={target['mode']}")
    manifest_path = Path(target["manifest_file"])
    manifest = read_private_json(manifest_path) if manifest_path.exists() else None
    if target.get("run_id") and (
        not manifest or target["run_id"] != manifest["run_id"]
    ):
        logger.warning("Cleanup refused because fixture ownership changed")
        raise RuntimeError("Fixture ownership no longer matches")
    application_present = target.get("stage") in ("application", "ready")
    if target["mode"] == "microk8s":
        kube = [*MICROK8S, "kubectl", "-n", target["namespace"]]
        helm = [*MICROK8S, "helm3", "-n", target["namespace"]]
        if application_present:
            releases = execute(
                [
                    *helm,
                    "list",
                    "--all",
                    "--short",
                    "--filter",
                    f"^{target['release']}$",
                ],
            ).splitlines()
            application_present = target["release"] in releases
            if not application_present:
                workloads = json.loads(
                    execute(
                        [
                            *kube,
                            "get",
                            "deployment,statefulset,job",
                            "-l",
                            f"app.kubernetes.io/instance={target['release']}",
                            "-o",
                            "json",
                        ],
                    )
                )["items"]
                if workloads:
                    logger.warning(
                        "Cleanup retained workloads without their owning release"
                    )
                    raise RuntimeError(
                        "Application workloads remain without their Helm release. Retain the fixture"
                    )
        owned_secrets = []
        for field in ("v3_secret", "hec_secret"):
            if not target.get(f"{field}_uid"):
                continue
            raw_secret = execute(
                [
                    *kube,
                    "get",
                    "secret",
                    target[field],
                    "--ignore-not-found",
                    "-o",
                    "json",
                ],
            )
            if raw_secret.strip():
                if json.loads(raw_secret)["metadata"]["uid"] != target[f"{field}_uid"]:
                    logger.warning("Cleanup retained a replaced fixture Secret")
                    raise RuntimeError(
                        "The fixture Secret was replaced. Do not delete it"
                    )
                owned_secrets.append(target[field])
        if application_present:
            statefulsets = json.loads(
                execute([*kube, "get", "statefulset", "-o", "json"])
            )["items"]
            for item in statefulsets:
                if (
                    item["metadata"]
                    .get("annotations", {})
                    .get("meta.helm.sh/release-name")
                    == target["release"]
                ):
                    retention = (
                        item["spec"]
                        .get("persistentVolumeClaimRetentionPolicy", {})
                        .get("whenDeleted", "Retain")
                    )
                    if retention != "Retain":
                        logger.warning(
                            "Cleanup refused because storage retention is not enabled"
                        )
                        raise RuntimeError(
                            "Storage must retain its claims before removing the owned workload"
                        )
    if application_present:
        result = observe_target(directory, target, manifest, "state")
        if not result["drained"]:
            logger.warning(
                "Cleanup retained the fixture because delivery is incomplete"
            )
            raise RuntimeError(
                "Outstanding delivery remains. Retain the fixture and storage"
            )
        if result["entries"] or result["foreign_entries"]:
            logger.warning("Cleanup retained the fixture because schedules remain")
            raise RuntimeError("Schedules remain. Retain the fixture and storage")
    # The setup script owns the job's simulators, just as for autodiscovery.
    # Removing this application must not remove that separately deployed cohort.
    if target["mode"] == "microk8s":
        if application_present:
            execute([*helm, "uninstall", target["release"], "--wait"])
            execute(
                [
                    *kube,
                    "delete",
                    "job",
                    "-l",
                    f"sc4snmp.integration.jitter-run={target['run_id']}",
                    "--wait=true",
                ],
            )
        for name in owned_secrets:
            execute([*kube, "delete", "secret", name])
    else:
        if Path(target["compose_file"]).exists():
            run_compose(target, "down")
    target["cleaned"] = True
    write_private(target_file, json.dumps(target))
    logger.info(
        "Owned test workloads removed after delivery accounting. Storage retained"
    )
