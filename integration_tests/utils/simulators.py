import argparse
import asyncio
import json
import logging
import os
import time
from pathlib import Path
from uuid import uuid4

from integration_tests.utils.deployment import (
    BASE_DIR,
    MICROK8S,
    _run_integration_command,
)
from integration_tests.utils.files import read_private_json, write_private

logger = logging.getLogger(__name__)


def authentication(version, credentials):
    from pysnmp.hlapi.v3arch.asyncio import (
        USM_AUTH_HMAC96_SHA,
        USM_PRIV_CFB128_AES,
        CommunityData,
        UsmUserData,
    )

    if version == "2c":
        return CommunityData(credentials["v2c"]["community"], mpModel=1)
    v3 = credentials["v3"]
    return UsmUserData(
        v3["username"],
        authKey=v3["auth_key"],
        privKey=v3["priv_key"],
        authProtocol=USM_AUTH_HMAC96_SHA,
        privProtocol=USM_PRIV_CFB128_AES,
    )


async def snmp_get(address, port, auth_data, oid_specs, timeout=2, retries=2):
    from pysnmp.hlapi.v3arch.asyncio import (
        ContextData,
        ObjectIdentity,
        ObjectType,
        SnmpEngine,
        UdpTransportTarget,
        get_cmd,
    )

    engine = SnmpEngine()
    try:
        target = await UdpTransportTarget.create(
            (address, port), timeout=timeout, retries=retries
        )
        return await get_cmd(
            engine,
            auth_data,
            target,
            ContextData(),
            *(ObjectType(ObjectIdentity(*oid_spec)) for oid_spec in oid_specs),
        )
    finally:
        engine.close_dispatcher()


async def wait_for_simulator(device, credentials, timeout=45):
    auth_data = authentication(device["version"], credentials)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        error, status, _, values = await snmp_get(
            device["address"],
            device["port"],
            auth_data,
            (("1.3.6.1.2.1.1.1.0",),),
            timeout=1,
            retries=0,
        )
        if (
            not error
            and not status
            and values
            and str(values[0][1]).startswith("SC4SNMP autodiscovery integration")
        ):
            logger.debug("A simulator answered SNMP")
            return
        await asyncio.sleep(1)
    logger.warning("Simulator SNMP readiness timed out")
    raise RuntimeError(f"{device.get('label', 'Simulator')} did not respond to SNMP")


async def probe_simulators(state, credentials):
    logger.info(
        f"Checking simulator SNMP readiness: backend={state['mode']}, "
        f"devices={len(state['devices'])}"
    )
    await asyncio.gather(
        *(wait_for_simulator(device, credentials) for device in state["devices"])
    )
    logger.info(f"All simulators answered SNMP: devices={len(state['devices'])}")


def deployed_simulator_pods(namespace, error_file):
    return json.loads(
        _run_integration_command(
            [
                *MICROK8S,
                "kubectl",
                "get",
                "pods",
                "-n",
                namespace,
                "-l",
                "sc4snmp.integration.simulator=true",
                "-o",
                "json",
            ],
            "Reading the job's simulator pods",
            error_file=error_file,
        )
    )["items"]


def capture_simulators(mode, namespace, manifest_path, credentials):
    manifest_path = Path(manifest_path).resolve()
    directory = manifest_path.parent
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    error_file = directory / "simulator-command-error.log"
    devices = []
    pods = deployed_simulator_pods(namespace, error_file)
    for pod in sorted(pods, key=lambda item: item["metadata"]["name"]):
        version = {"v2c": "2c", "v3": "3"}[pod["metadata"]["labels"]["variation"]]
        devices.append(
            {
                "label": f"IP{len(devices) + 1}",
                "name": pod["metadata"]["name"],
                "uid": pod["metadata"]["uid"],
                "address": pod["status"]["podIP"],
                "port": 161,
                "version": version,
                "credential_ref": "v2c" if version == "2c" else "v3",
            }
        )
    credential_path = directory / "credentials.json"
    write_private(credential_path, json.dumps(credentials))
    write_private(
        manifest_path,
        json.dumps(
            {
                "mode": mode,
                "namespace": namespace,
                "credentials_file": str(credential_path),
                "devices": devices,
            }
        ),
    )
    logger.info(f"Recorded the job's simulator endpoints: devices={len(devices)}")


def load_simulators(directory, mode):
    source_path = Path(
        os.getenv(
            "SIMULATOR_MANIFEST",
            str(BASE_DIR / ".simulators" / mode / "endpoints.json"),
        )
    )
    if not source_path.is_file():
        raise RuntimeError(
            "Run the existing integration setup before selecting jitter tests"
        )
    state = read_private_json(source_path)
    if state["mode"] != mode:
        raise RuntimeError("The simulator setup belongs to a different deployment mode")
    # Each job deploys its own six SNMP simulators. Use five of them
    # for jitter without creating a second deployment or changing discovery.
    selected = []
    for version, count in (("2c", 3), ("3", 2)):
        selected.extend(
            [d for d in state["devices"] if d["version"] == version][:count]
        )
    state["devices"] = selected
    if len(state["devices"]) != 5:
        raise RuntimeError("The job needs three v2c and two v3 simulator endpoints")
    directory = Path(directory).resolve()
    directory.mkdir(mode=0o700)
    error_file = directory / "simulator-command-error.log"
    pods = {
        pod["metadata"]["name"]: pod
        for pod in deployed_simulator_pods(state["namespace"], error_file)
    }
    for index, device in enumerate(state["devices"], 1):
        pod = pods.get(device["name"])
        if (
            not pod
            or pod["metadata"]["uid"] != device["uid"]
            or pod["status"].get("podIP") != device["address"]
        ):
            raise RuntimeError(
                "The job's simulator deployment changed. Run setup again"
            )
        device["label"] = f"IP{index}"
    credentials = read_private_json(state["credentials_file"])
    asyncio.run(probe_simulators(state, credentials))
    credential_path = directory / "credentials.json"
    write_private(credential_path, json.dumps(credentials))
    state.update(
        {
            # A new pytest session gets fresh application storage even when
            # it uses the same simulator deployment prepared for this job.
            "run_id": f"jitter-{uuid4().hex[:12]}",
            "credentials_file": str(credential_path),
            "manifest_path": str(directory / "endpoints.json"),
            "ready": True,
        }
    )
    write_private(state["manifest_path"], json.dumps(state))
    logger.info(f"Using the job's simulator deployment: backend={mode}, devices=5")
    return state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("microk8s", "docker-compose"), required=True)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    capture_simulators(
        args.mode,
        args.namespace,
        args.manifest,
        {
            "v2c": {"community": os.environ["SIM_COMMUNITY"]},
            "v3": {
                "username": os.environ["SIM_USER"],
                "auth_key": os.environ["SIM_AUTH"],
                "priv_key": os.environ["SIM_PRIV"],
                "auth_protocol": "SHA",
                "priv_protocol": "AES",
                "security_engine_id": os.environ["SIM_ENGINE"],
            },
        },
    )


if __name__ == "__main__":
    main()
