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
    DOCKER,
    MICROK8S,
    _run_integration_command,
    application_context,
    helm_command,
    probe_application,
)
from integration_tests.utils.files import read_private_json, write_private

logger = logging.getLogger(__name__)
ROOT = BASE_DIR.parent


def run(arguments, content=None, timeout=600, env=None):
    return _run_integration_command(
        arguments,
        "Application setup command",
        content=content,
        timeout=timeout,
        env=env,
    )


def wait_for_application(target, manifest):
    logger.info(f"Waiting for an empty isolated application: backend={target['mode']}")
    env = compose_environment(target) if target["mode"] == "docker-compose" else None
    execute = partial(run, timeout=45, env=env)
    deadline = time.monotonic() + 600
    snapshot = {}
    while time.monotonic() < deadline:
        try:
            context = application_context(target, execute)
            target["component_uids"] = context["component_uids"]
            snapshot = probe_application(
                context,
                manifest["devices"],
                "state",
                execute,
                component="worker-sender",
            )
            if snapshot["drained"]:
                if snapshot["entries"] or snapshot["foreign_entries"]:
                    raise RuntimeError("The isolated application did not start empty")
                logger.info("The isolated application is ready with no pending work")
                return
        except (RuntimeError, subprocess.TimeoutExpired):
            pass
        time.sleep(1)
    logger.warning(
        f"Application readiness timed out: workers={snapshot.get('workers')} "
        f"complete={snapshot.get('worker_replies_complete')} "
        f"queued={snapshot.get('queued')} unacked={snapshot.get('unacked')}. "
        "Owned state is retained"
    )
    raise RuntimeError("The isolated application did not become ready and empty")


def prepare_kubernetes(
    directory, target, splunk, manifest, image, *, ha=False, mongo_inventory=False
):
    namespace_name = target["namespace"]
    kube = [*MICROK8S, "kubectl", "-n", namespace_name]
    helm = [*MICROK8S, "helm3", "-n", namespace_name]
    execute = run
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
    execute([*MICROK8S, "kubectl", "create", "namespace", namespace_name])
    credentials = read_private_json(manifest["credentials_file"])["v3"]
    hec = splunk["hec"]
    secret_data = {
        "v3_secret": {
            "userName": credentials["username"],
            "authKey": credentials["auth_key"],
            "authProtocol": "SHA",
            "privKey": credentials["priv_key"],
            "privProtocol": "AES",
            "securityEngineId": credentials["security_engine_id"],
        },
        "hec_secret": {"hec_token": hec["token"]},
    }
    if mongo_inventory:
        defaults = yaml.safe_load(
            (ROOT / "charts/splunk-connect-for-snmp/values.yaml").read_text()
        )
        backend = defaults["UI"]["backEnd"]
        password_hash = execute(
            [
                *DOCKER,
                "run",
                "--rm",
                "--network=none",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--entrypoint=python",
                f"{backend['repository']}:{backend['tag']}",
                "-c",
                "import secrets\nfrom argon2 import PasswordHasher\n"
                "print(PasswordHasher().hash(secrets.token_urlsafe(32)))",
            ]
        ).strip()
        target["ui_secret"] = f"{release}-ui-auth"
        secret_data["ui_secret"] = {
            "username": "jitter-integration",
            "password_hash": password_hash,
            "jwt_secret": secrets.token_hex(32),
        }
    for field, data in secret_data.items():
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
        execute(
            [*kube, "create", "-f", "-"],
            json.dumps(secret),
        )
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
    if mongo_inventory:
        ui_directory = directory / "ui-values"
        ui_directory.mkdir(mode=0o700)
        overrides["UI"] = {
            "auth": {"enabled": True, "existingSecret": target["ui_secret"]},
            "valuesFileDirectory": str(ui_directory),
        }
    if ha:
        overrides["redis"].update(
            architecture="replication",
            replicaCount=3,
            sentinel={"replicaCount": 3, "quorum": 2},
        )
        overrides["mongodb"].update(mode="replication", replicaCount=3)
        overrides["mongodb"]["auth"]["enabled"] = True
        logger.info("Preparing authenticated Redis/Sentinel and MongoDB replicas")
    write_private(overrides_file, yaml.safe_dump(overrides))
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
            "--timeout=10m",
        ],
        timeout=660,
    )
    inventory_selector = (
        f"app.kubernetes.io/instance={release},app.kubernetes.io/component=inventory"
    )
    execute(
        [
            *kube,
            "wait",
            "--for=condition=Complete",
            "job",
            "-l",
            inventory_selector,
            "--timeout=600s",
        ],
        timeout=660,
    )
    execute(
        [
            *kube,
            "delete",
            "job",
            "-l",
            inventory_selector,
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


def prepare(
    mode,
    directory,
    splunk,
    image="snmp-local:latest",
    *,
    ha=False,
    mongo_inventory=False,
):
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
        "run_id": manifest["run_id"],
        "namespace": manifest["run_id"] if mode == "microk8s" else "sc4snmp",
        "manifest_file": str(directory / "simulators/endpoints.json"),
        "event_index": splunk.get("event_index", "netops"),
        "metric_index": splunk.get("metric_index", "netmetrics"),
    }
    write_private(directory / "target.json", json.dumps(target))
    if mode == "docker-compose":
        target.update(prepare_compose(directory, manifest["run_id"], image, splunk))
        write_private(directory / "target.json", json.dumps(target))
        start_compose(target, read_private_json(manifest["credentials_file"]))
    else:
        prepare_kubernetes(
            directory,
            target,
            splunk,
            manifest,
            image,
            ha=ha,
            mongo_inventory=mongo_inventory,
        )
    wait_for_application(target, manifest)
    write_private(directory / "target.json", json.dumps(target))
    logger.info(
        f"Isolated polling environment prepared: backend={mode}, "
        f"devices={len(manifest['devices'])}"
    )


def remove_application(target):
    logger.info(f"Removing disposable test application: backend={target['mode']}")
    if target["mode"] == "docker-compose":
        run_compose(target, "down")
    else:
        run(
            [
                *MICROK8S,
                "helm3",
                "uninstall",
                target["release"],
                "--namespace",
                target["namespace"],
                "--wait",
                "--timeout=180s",
            ],
        )
    logger.info("Disposable application removed, simulator deployment retained")
