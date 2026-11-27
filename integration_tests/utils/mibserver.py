import json
import logging
import shutil
from pathlib import Path

from integration_tests.utils.splunk_test_utils import (
    BASE_DIR,
    MIB_INDEX_REFRESH_MIB,
    MIB_INDEX_REFRESH_ROW,
    _fetch_mib_refresh_index,
    _run_integration_command,
    _sc4snmp_compose_command,
    _wait_for_mib_refresh_result,
    exec_sc4snmp_component,
    restart_sc4snmp_component,
)

logger = logging.getLogger(__name__)

MIBSERVER_RESOURCE = "deployment/snmp-mibserver"
MIBSERVER_FIXTURES_DIR = BASE_DIR / "fixtures" / "mibserver" / "mibs"
LOCAL_MIB_INDEX_ROWS = {
    "SC4SNMP-TEST-MIB,1.3.6.1.4.1.99999",
    "SC4SNMP-TEST-MIB,1.3.6.1.4.1.99999.100",
    "SC4SNMP-TEST-MIB,1.3.6.1.4.1.99999.101",
    "SC4SNMP-TEST-TC,1.3.6.1.4.1.99998",
    "SC4SNMP-TEST-EXT-MIB,1.3.6.1.4.1.99996",
    "SC4SNMP-TEST-V1-MIB,1.3.6.1.4.1.99997",
}


def get_mibserver_url(deployment):
    if deployment == "microk8s":
        return "http://snmp-mibserver"
    if deployment == "docker-compose":
        return "http://snmp-mibserver:8000"
    raise ValueError(f"Unsupported SC4SNMP deployment: {deployment}")


def run_mib_python(deployment, script, *, mibserver=False):
    """Run a check inside the deployed compiler or consumer environment."""
    command = (
        ["sh", "-c", "exec /app/.cache/*/bin/python -"]
        if mibserver
        else ["/app/.venv/bin/python", "-"]
    )
    return exec_sc4snmp_component(
        deployment,
        command,
        "checking local MIB compilation",
        compose_service="snmp-mibserver" if mibserver else "scheduler",
        kubernetes_resource=(
            MIBSERVER_RESOURCE
            if mibserver
            else "deployment/snmp-splunk-connect-for-snmp-scheduler"
        ),
        input_text=script,
    )


def configured_local_mib_directory(deployment):
    if deployment == "microk8s":
        local_mibs = _microk8s_local_mib_directory()
    elif deployment == "docker-compose":
        local_mibs = BASE_DIR / "local_mibs" / "part9"
    else:
        raise ValueError(f"Unsupported SC4SNMP deployment: {deployment}")
    if not local_mibs.is_dir():
        raise RuntimeError("Run the dedicated mibserver integration setup first")
    _check_local_mib_mount(deployment, local_mibs)
    return local_mibs


def prepare_local_mib_environment(deployment):
    local_mibs = configured_local_mib_directory(deployment)
    index = _wait_for_mib_refresh_result(
        lambda: _fetch_mib_refresh_index(deployment),
        lambda content: LOCAL_MIB_INDEX_ROWS <= set(content.splitlines()),
        "the local compilation fixture rows in the live MIB index",
    )
    logger.info("Local MIBs compiled from %s", local_mibs)
    return index


def _microk8s_local_mib_directory():
    local_mibs = BASE_DIR / "local_mibs" / "part9"
    if not local_mibs.is_dir():
        raise RuntimeError("Run the dedicated mibserver integration setup first")

    volume_name = _run_integration_command(
        [
            "sudo",
            "microk8s",
            "kubectl",
            "get",
            "pvc/snmp-mibserver",
            "-n",
            "sc4snmp",
            "-o",
            "jsonpath={.spec.volumeName}",
        ],
        "reading the configured local-MIB claim",
    ).strip()
    if not volume_name:
        raise RuntimeError("The configured local-MIB claim is not bound")
    host_path = _run_integration_command(
        [
            "sudo",
            "microk8s",
            "kubectl",
            "get",
            f"pv/{volume_name}",
            "-o",
            "jsonpath={.spec.hostPath.path}",
        ],
        "reading the configured local-MIB volume",
    ).strip()
    if host_path != str(local_mibs):
        raise RuntimeError(
            "The deployed local-MIB volume does not match integration values"
        )
    return local_mibs


def _check_local_mib_mount(deployment, local_mibs_dir):
    mount_path = "/app/new_mibs/src/vendor"
    if deployment == "microk8s":
        spec = json.loads(
            _run_integration_command(
                [
                    "sudo",
                    "microk8s",
                    "kubectl",
                    "get",
                    "deployment/snmp-mibserver",
                    "-n",
                    "sc4snmp",
                    "-o",
                    "jsonpath={.spec.template.spec}",
                ],
                "reading the deployed mibserver volume configuration",
            )
        )
        container = next(c for c in spec["containers"] if c["name"] == "mibserver")
        mount = next(
            m for m in container["volumeMounts"] if m["mountPath"] == mount_path
        )
        volume = next(v for v in spec["volumes"] if v["name"] == mount["name"])
        configured = (
            volume.get("persistentVolumeClaim", {}).get("claimName") == "snmp-mibserver"
            and not mount.get("readOnly", False)
            and container["securityContext"].get("readOnlyRootFilesystem") is False
        )
    else:
        container_id = _run_integration_command(
            _sc4snmp_compose_command("ps", "-q", "snmp-mibserver"),
            "finding the deployed mibserver container",
        ).strip()
        mounts = json.loads(
            _run_integration_command(
                [
                    "sudo",
                    "docker",
                    "inspect",
                    "--format",
                    "{{json .Mounts}}",
                    container_id,
                ],
                "reading the deployed mibserver bind mount",
            )
        )
        configured = any(
            mount["Destination"] == mount_path
            and mount["Type"] == "bind"
            and Path(mount["Source"]).resolve() == Path(local_mibs_dir).resolve()
            and mount["RW"]
            for mount in mounts
        )
    if not configured:
        raise RuntimeError("The mibserver is not using the production local-MIB mount")


def restart_mibserver(deployment):
    restart_sc4snmp_component(
        deployment,
        compose_service="snmp-mibserver",
        kubernetes_resource=MIBSERVER_RESOURCE,
        reconfigure=False,
    )


def wait_for_refresh_mib_index_row(deployment, expected_present):
    def row_state_matches(index_content):
        index_rows = {line.strip() for line in index_content.splitlines()}
        return bool(index_rows) and (
            (MIB_INDEX_REFRESH_ROW in index_rows) == expected_present
        )

    expectation = "appear in" if expected_present else "be absent from"
    return _wait_for_mib_refresh_result(
        lambda: _fetch_mib_refresh_index(deployment),
        row_state_matches,
        f"{MIB_INDEX_REFRESH_ROW!r} to {expectation} the live MIB index",
    )


def install_refresh_test_mib(deployment, local_mibs_dir):
    vendor_dir = Path(local_mibs_dir) / MIB_INDEX_REFRESH_MIB.parent.name
    vendor_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MIB_INDEX_REFRESH_MIB, vendor_dir / MIB_INDEX_REFRESH_MIB.name)
    vendor_dir.chmod(0o755)
    restart_mibserver(deployment)
    wait_for_refresh_mib_index_row(deployment, expected_present=True)
