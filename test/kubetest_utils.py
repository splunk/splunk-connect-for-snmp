from kubetest.client import TestClient
import logging

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
