import json
import logging
import os
import subprocess
from pathlib import Path
from uuid import uuid4

from integration_tests.utils.files import write_private

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
INTEGRATION_TEST_TIMEOUT = 180
DOCKER = ["docker"] if os.geteuid() == 0 else ["sudo", "docker"]
MICROK8S = ["microk8s"] if os.geteuid() == 0 else ["sudo", "microk8s"]
APP_PYTHON = "/app/.venv/bin/python"
PROBE_SHELL = [
    "sh",
    "-c",
    '. /app/construct-connection-strings.sh >/dev/null\nexec "$@"',
    "jitter-observer",
]


def probe_program(request):
    return (
        Path(__file__)
        .with_name("application_probe.py")
        .read_text()
        .replace("request = json.load(sys.stdin)", f"request = {request!r}")
    )


def application_context(target, run):
    names = ("scheduler", "worker-poller", "worker-sender")
    context = {"component_uids": {}, "images": {}}
    if target["mode"] == "microk8s":
        kube = [*MICROK8S, "kubectl", "-n", target["namespace"]]
        selector = f"app.kubernetes.io/instance={target['release']}"
        deployments = json.loads(run([*kube, "get", "deployment", "-o", "json"]))[
            "items"
        ]
        components = {
            item["metadata"]["labels"].get("app.kubernetes.io/component"): item
            for item in deployments
            if item["metadata"].get("labels", {}).get("app.kubernetes.io/instance")
            == target["release"]
        }
        if not all(name in components for name in names):
            raise RuntimeError("The owned application components are not ready")
        for name in names:
            metadata = components[name]["metadata"]
            if (
                metadata.get("annotations", {}).get("meta.helm.sh/release-name")
                != target["release"]
            ):
                raise RuntimeError("Application ownership no longer matches")
            expected = target.get("component_uids", {}).get(name)
            if expected and metadata["uid"] != expected:
                raise RuntimeError("An owned application component was replaced")
            context["component_uids"][name] = metadata["uid"]
            context["images"][name] = components[name]["spec"]["template"]["spec"][
                "containers"
            ][0]["image"]
        context.update(kube=kube, selector=selector)
        context["deployments"] = {
            name: components[name]["metadata"]["name"] for name in names
        }
        context["exec_prefixes"] = {
            name: [
                *kube,
                "exec",
                "-i",
                f"deployment/{components[name]['metadata']['name']}",
                "--",
                *PROBE_SHELL,
            ]
            for name in names
        }
        context["expected_workers"] = sum(
            components[name]["spec"].get("replicas", 1) for name in names[1:]
        )
        context["expected_workers"] += sum(
            item["spec"].get("replicas", 1)
            for item in deployments
            if item["metadata"]["name"] == "ui-backend-worker-deployment"
            and item["metadata"].get("annotations", {}).get("meta.helm.sh/release-name")
            == target["release"]
        )
    else:
        from integration_tests.utils.compose import compose_command

        compose = compose_command(target)
        configuration = json.loads(run([*compose, "config", "--format=json"]))
        context["compose"] = compose
        context["images"] = {
            name: configuration["services"][name]["image"] for name in names
        }
        context["exec_prefixes"] = {
            name: [*compose, "exec", "-T", name, *PROBE_SHELL] for name in names
        }
        # Observers must not consume the sender's fixed worker memory budget.
        # Reuse the scheduler configuration in a separate, disposable process.
        context["observer_prefix"] = [
            *compose,
            "run",
            "--rm",
            "--no-deps",
            "-T",
            "--entrypoint",
            "sh",
            "scheduler",
            *PROBE_SHELL[1:],
        ]
        context["expected_workers"] = sum(
            configuration["services"][name].get("deploy", {}).get("replicas", 1)
            for name in names[1:]
        )
    return context


def probe_application(
    context, devices, action, run, *, component="worker-poller", **data
):
    request = {
        "devices": devices,
        "action": action,
        "expected_workers": context["expected_workers"],
        **data,
    }
    if action in ("failover_redis", "step_down_mongo") and "kube" in context:
        deployment = json.loads(
            run(
                [
                    *context["kube"],
                    "get",
                    "deployment",
                    context["deployments"]["scheduler"],
                    "-o",
                    "json",
                ]
            )
        )
        spec = deployment["spec"]["template"]["spec"]
        spec["restartPolicy"] = "Never"
        name = f"jitter-probe-{uuid4().hex[:12]}"
        spec["containers"][0]["name"] = name
        spec["containers"][0]["command"] = [
            *PROBE_SHELL,
            APP_PYTHON,
            "-c",
            probe_program(request),
        ]
        spec["containers"][0]["args"] = []
        logger.info(f"Running {action} from a disposable observer Pod")
        try:
            output = run(
                [
                    *context["kube"],
                    "run",
                    name,
                    "--restart=Never",
                    "--attach=true",
                    "--quiet=true",
                    "--image",
                    context["images"]["scheduler"],
                    "--overrides",
                    json.dumps({"apiVersion": "v1", "spec": spec}),
                ],
                timeout=data.get("timeout", INTEGRATION_TEST_TIMEOUT) + 60,
            )
        finally:
            run(
                [
                    *context["kube"],
                    "delete",
                    "pod",
                    name,
                    "--ignore-not-found=true",
                    "--wait=false",
                ]
            )
    else:
        prefix = context["exec_prefixes"][component]
        if action in (
            "state",
            "snapshot",
            "drained",
            "failover_redis",
            "step_down_mongo",
        ):
            prefix = context.get("observer_prefix", prefix)
        output = run(
            [*prefix, APP_PYTHON, "-"],
            probe_program(request),
        )
    for line in reversed(output.splitlines()):
        if line.startswith("JITTER_RESULT="):
            return json.loads(line.removeprefix("JITTER_RESULT="))
    raise RuntimeError("The owned application did not return an observation")


def close_observer(process):
    if process is None:
        return
    if not process.stdin.closed:
        try:
            process.stdin.write("\n")
            process.stdin.close()
        except BrokenPipeError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        logger.warning("Observer did not exit after input closed, terminating it")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning("Observer did not terminate, killing it")
            process.kill()
            process.wait(timeout=5)


def helm_command(target, action, *values_files):
    return [
        *MICROK8S,
        "helm3",
        action,
        target["release"],
        str(target.get("chart", BASE_DIR.parent / "charts/splunk-connect-for-snmp")),
        "-n",
        target["namespace"],
        *(argument for path in values_files for argument in ("-f", str(path))),
    ]


def _run_integration_command(
    command,
    description,
    timeout=INTEGRATION_TEST_TIMEOUT,
    *,
    include_stderr=False,
    content=None,
    env=None,
    error_file=None,
):
    options = {}
    if content is not None:
        options["input"] = content
    if env is not None:
        options["env"] = env
    logger.debug(f"Running integration command with timeout={timeout}")
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            **options,
        )
    except subprocess.TimeoutExpired as exc:
        logger.warning(f"Integration command timed out after {timeout} seconds")
        if error_file is None:
            raise
        result = exc
        failure = "timed out"
    else:
        if result.returncode == 0:
            logger.debug(
                f"Integration command completed with return_code={result.returncode}"
            )
            if include_stderr:
                return result.stdout + result.stderr
            return result.stdout
        logger.warning(
            f"Integration command failed with return_code={result.returncode}"
        )
        if error_file is None:
            details = (result.stderr or result.stdout).strip()
            raise RuntimeError(f"{description} failed: {details[-2000:]}")
        failure = "failed"
    output = result.stdout or ""
    errors = result.stderr or ""
    if isinstance(output, bytes):
        output = output.decode(errors="replace")
    if isinstance(errors, bytes):
        errors = errors.decode(errors="replace")
    write_private(error_file, output + "\n" + errors)
    raise RuntimeError(
        f"{description} {failure}. Protected evidence was retained"
    ) from None


def _sc4snmp_compose_command(
    *arguments,
    compose_file=None,
    env_file=None,
    project=None,
    docker=None,
):
    compose_dir = BASE_DIR / "docker_compose"
    command = [*(docker if docker is not None else ["sudo", "docker"]), "compose"]
    if project is not None:
        command.extend(["--project-name", project])
    return [
        *command,
        "-f",
        str(compose_file or compose_dir / "docker-compose.yaml"),
        "--env-file",
        str(env_file or compose_dir / ".env"),
        *arguments,
    ]


def wait_for_microk8s_rollout(
    kubernetes_resource,
    description,
    *,
    namespace="sc4snmp",
    timeout=INTEGRATION_TEST_TIMEOUT,
    kubectl=None,
    error_file=None,
):
    logger.info("Waiting for Kubernetes rollout")
    _run_integration_command(
        [
            *(kubectl if kubectl is not None else ["sudo", "microk8s", "kubectl"]),
            "rollout",
            "status",
            kubernetes_resource,
            "-n",
            namespace,
            f"--timeout={timeout}s",
        ],
        f"waiting for the {description} Kubernetes rollout",
        timeout=timeout,
        error_file=error_file,
    )
    logger.info("Kubernetes rollout completed")


def restart_sc4snmp_component(
    deployment: str,
    *,
    compose_service: str,
    kubernetes_resource: str,
    namespace="sc4snmp",
    timeout=INTEGRATION_TEST_TIMEOUT,
    kubectl=None,
    compose_file=None,
    env_file=None,
    project=None,
    docker=None,
    env=None,
    error_file=None,
    restart_only=False,
) -> None:
    logger.info("Restarting application component")
    if deployment == "microk8s":
        _run_integration_command(
            [
                *(kubectl if kubectl is not None else ["sudo", "microk8s", "kubectl"]),
                "rollout",
                "restart",
                kubernetes_resource,
                "-n",
                namespace,
            ],
            f"restarting the {compose_service} Kubernetes resource",
            timeout=timeout,
            error_file=error_file,
        )
        wait_for_microk8s_rollout(
            kubernetes_resource,
            compose_service,
            namespace=namespace,
            timeout=timeout,
            kubectl=kubectl,
            error_file=error_file,
        )
    elif deployment == "docker-compose":
        arguments = (
            ["restart", compose_service]
            if restart_only
            else ["up", "-d", "--force-recreate", "--no-deps", compose_service]
        )
        _run_integration_command(
            _sc4snmp_compose_command(
                *arguments,
                compose_file=compose_file,
                env_file=env_file,
                project=project,
                docker=docker,
            ),
            f"{'restarting' if restart_only else 'recreating'} the {compose_service} "
            "Docker Compose service",
            timeout=timeout,
            env=env,
            error_file=error_file,
        )
    else:
        raise ValueError(f"Unsupported SC4SNMP deployment: {deployment}")
    logger.info("Application component restart completed")
