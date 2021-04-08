from kubetest.client import TestClient
import logging
import subprocess
import requests

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
        "--from-literal=SPLUNK_HEC_TLS_SKIP_VERIFY=true",
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


def extract_splunk_password_from_deployment(local_splunk_deployment):
    # we assume a deployment with at least one pod. Only the first pod
    # will be considered.
    env_variables = local_splunk_deployment.get_pods()[0].get_containers()[0].obj.env
    return next(e.value for e in env_variables if e.name == "SPLUNK_PASSWORD")


def setup_splunk(proxy, ip, password):
    url = f"https://{ip}:8089/services/data/indexes"
    data = {"datatype": "event", "name": "netops", "auth_settings": []}

    logger.info(f"{url}")
    try:
        #url = f"https://{ip}:8089/services/data/indexes"
        #data = {"datatype": "event", "name": "netops"}
        r = requests.post(url=url, json=data, auth=("admin", password))
        logger.info(f"{r.status_code}")
    except requests.ConnectionError as e:
        logger.error(f"Connection error: {e}")

# index_type: 'event' or 'metric'
# splunk_url: e.g. https://192.168.0.1:8089
def create_splunk_index(splunk_url, index_name, index_type):
    data = {
        "name": index_name,
        "datatype": index_type
    }

    indexes_endpoint = splunk_url + '/services/data/indexes'

    response = requests.post(url=indexes_endpoint, data=data, auth=('admin', 'changedpassword'), verify=False)

    return response.status_code
