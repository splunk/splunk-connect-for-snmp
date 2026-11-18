import json
import logging
import os
import re
from pathlib import Path

import yaml

from integration_tests.utils.deployment import (
    BASE_DIR,
    DOCKER,
    _run_integration_command,
    _sc4snmp_compose_command,
)
from integration_tests.utils.files import write_container_file, write_private

logger = logging.getLogger(__name__)

ROOT = BASE_DIR.parent

SERVICES = (
    "redis",
    "mongo",
    "snmp-mibserver",
    "inventory",
    "scheduler",
    "worker-poller",
    "worker-sender",
)
APP_SERVICES = ("inventory", "scheduler", "worker-poller", "worker-sender")


def compose_command(target):
    return _sc4snmp_compose_command(
        project=target["project"],
        env_file=target["env_file"],
        compose_file=target["compose_file"],
        docker=DOCKER,
    )


def compose_environment(target):
    defined = {
        match.group(1)
        for line in Path(target["env_file"]).read_text().splitlines()
        if (match := re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", line))
    }
    return {key: value for key, value in os.environ.items() if key not in defined}


def run_compose(target, *arguments):
    return _run_integration_command(
        [*compose_command(target), *arguments],
        "Owned Compose command",
        timeout=600,
        env=compose_environment(target),
    )


def prepare_compose(directory, project, image, splunk):
    logger.info("Preparing isolated Docker Compose deployment")
    directory = Path(directory).resolve()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    source = ROOT / "docker_compose/docker-compose.yaml"
    defaults_file = source.parent / ".env"
    defaults = defaults_file.read_text()
    hec = splunk["hec"]
    config = directory / "config.yaml"
    inventory = directory / "inventory.csv"
    secrets = directory / "app-secrets"
    local_mibs = directory / "local-mibs"
    token = directory / "hec-token"
    secrets.mkdir(mode=0o700)
    if os.geteuid() == 0:
        os.chown(secrets, 10001, 10001)
    elif os.geteuid() != 10001:
        secrets.chmod(0o750)
    local_mibs.mkdir(mode=0o755)
    write_container_file(config, yaml.safe_dump({"profiles": {}, "groups": {}}))
    write_container_file(
        inventory, "address,port,version,community,secret,profiles,delete\n"
    )
    write_container_file(token, hec["token"])
    overrides = {
        "SCHEDULER_CONFIG_FILE_ABSOLUTE_PATH": str(config),
        "INVENTORY_FILE_ABSOLUTE_PATH": str(inventory),
        "SECRET_FOLDER_PATH": str(secrets),
        "LOCAL_MIBS_PATH": str(local_mibs),
        "SPLUNK_HEC_HOST": hec["host"],
        "SPLUNK_HEC_PORT": str(hec.get("port", 8088)),
        "SPLUNK_HEC_PROTOCOL": hec.get("scheme", "https"),
        "SPLUNK_HEC_TOKEN": hec["token"],
        "SPLUNK_HEC_TOKEN_SECRET_FILE": str(token),
        "SPLUNK_HEC_INSECURESSL": str(not hec.get("verify", True)).lower(),
        "SPLUNK_HEC_INDEX_EVENTS": splunk.get("event_index", "netops"),
        "SPLUNK_HEC_INDEX_METRICS": splunk.get("metric_index", "netmetrics"),
        "ENABLE_WORKER_POLLER_SECRETS": "true",
        "POLL_BASE_PROFILES": "false",
        "ENABLE_FULL_WALK": "false",
        "CONFIG_FROM_MONGO": "false",
        "POLLING_JITTER_ENABLED": "false",
        "POLLING_JITTER_WINDOW_SECONDS": "60",
        "METRICS_INDEXING_ENABLED": "true",
        "COMPOSE_PROFILES": "",
    }
    env_file = directory / ".env"
    env_lines = []
    for key, value in overrides.items():
        quoted = str(value).replace("'", "\\'")
        env_lines.append(f"{key}='{quoted}'")
    write_private(env_file, defaults.rstrip() + "\n\n" + "\n".join(env_lines) + "\n")
    model = yaml.safe_load(source.read_text())
    selected = {name: model["services"][name] for name in SERVICES}
    for name, service in selected.items():
        for field in ("container_name", "dns", "ports", "networks"):
            service.pop(field, None)
        service["networks"] = ["default"]
        dependencies = service.get("depends_on", [])
        dependencies = [
            dependency for dependency in dependencies if dependency in SERVICES
        ]
        if dependencies:
            service["depends_on"] = dependencies
        else:
            service.pop("depends_on", None)
        if name in APP_SERVICES:
            service["image"] = image
            if os.geteuid() not in (0, 10001):
                service.setdefault("group_add", []).append(str(os.getegid()))
        for key, value in service.get("environment", {}).items():
            if isinstance(value, bool):
                service["environment"][key] = str(value).lower()
    volumes = {
        mount.split(":", 1)[0]
        for service in selected.values()
        for mount in service.get("volumes", [])
        if isinstance(mount, str) and mount.split(":", 1)[0] in model.get("volumes", {})
    }
    rendered = {
        "services": selected,
        "networks": {"default": {"labels": {"sc4snmp.integration.jitter": project}}},
        "volumes": {name: model["volumes"][name] for name in sorted(volumes)},
        "configs": model.get("configs", {}),
        "secrets": model.get("secrets", {}),
    }
    owned_compose = directory / "docker-compose.yaml"
    write_private(owned_compose, yaml.safe_dump(rendered, sort_keys=False))
    target = {
        "mode": "docker-compose",
        "project": project,
        "compose_file": str(owned_compose),
        "env_file": str(env_file),
        "config_file": str(config),
        "inventory_file": str(inventory),
        "v3_secret": "jitter-v3",
        "event_index": splunk.get("event_index", "netops"),
        "metric_index": splunk.get("metric_index", "netmetrics"),
    }
    run_compose(target, "config", "--quiet")
    run_compose(target, "up", "-d", "redis", "mongo", "snmp-mibserver")
    logger.info("Isolated Docker Compose deployment prepared")
    return target


def start_compose(target, credentials):
    logger.info("Starting Docker Compose application")
    v3 = credentials["v3"]
    secret_file = Path(target["compose_file"]).parent / "app-secrets/secrets.json"
    write_container_file(
        secret_file,
        json.dumps(
            {
                target["v3_secret"]: {
                    "username": v3["username"],
                    "authkey": v3["auth_key"],
                    "authprotocol": v3.get("auth_protocol", "SHA"),
                    "privkey": v3["priv_key"],
                    "privprotocol": v3.get("priv_protocol", "AES"),
                }
            }
        ),
    )
    run_compose(target, "up", "-d", "scheduler", "worker-poller", "worker-sender")
    logger.info("Docker Compose application started")
