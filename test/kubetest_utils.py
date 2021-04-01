from kubetest.client import TestClient
import logging
import subprocess

logger = logging.getLogger(__name__)


def create_deployment(kube: TestClient, yaml_path):
    logger.info(f"Deploying {yaml_path}")
    deployment = kube.load_deployment(yaml_path)
    deployment.create()
    deployment.wait_until_ready()
    deployment.refresh()
    return deployment


def create_service(kube: TestClient, yaml_path):
    logger.info(f"Deploying {yaml_path}")
    service = kube.load_service(yaml_path)
    service.create()
    service.wait_until_ready()
    service.refresh()
    return service


def create_kubernetes_secret(secret_name, splunk_url, token):
    command = [
        "microk8s",
        "kubectl",
        "create",
        "secret",
        "generic",
        secret_name,
        f"--from-literal=SPLUNK_HEC_URL={splunk_url}",
        "--from-literal=SPLUNK_HEC_TLS_VERIFY=true",
        f"--from-literal=SPLUNK_HEC_TOKEN={token}",
        "-o",
        "yaml",
        "--dry-run=client",
    ]

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = process.communicate()
    logger.info(f"Create secrete output = {out}")
    logger.info(f"Create secret error stream: {err}")

    secret_yaml = "/tmp/remote-secret.yaml"
    with open(secret_yaml, "wb+") as secret_yaml_file:
        secret_yaml_file.write(out)

    return process.returncode == 0, secret_yaml
