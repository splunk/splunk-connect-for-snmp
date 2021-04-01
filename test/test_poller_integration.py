from kubernetes.client import V1ConfigMap
import pytest

from test.kubetest_utils import create_service, create_deployment

import logging

logger = logging.getLogger(__name__)

# even if this should be the default behavior (the documentation claims
# the default value of the "kubeconfig" fixture is "~/.kube/config" in my
# case it was always None (not sure why). This seems to be working.
# NOTE: I had issues with the default configuration, in particular my ~/.kube/config
#       for some reason had "current-context" empty (not sure why).
#       Use the command "microk8s config > ~/.kube/config" to properly configure
#       your current Kubernetes instance.
@pytest.fixture
def kubeconfig():
    return "~/.kube/config"


@pytest.fixture
def rabbitmq_deployment(kube):
    return create_deployment(kube, "../deploy/sc4snmp/rq-deployment.yaml")


@pytest.fixture
def rabbitmq_service(kube):
    return create_service(kube, "../deploy/sc4snmp/rq-service.yaml")


@pytest.fixture
def mongo_deployment(kube):
    return create_deployment(kube, "../deploy/sc4snmp/mongo-deployment.yaml")


@pytest.fixture
def mongo_service(kube):
    return create_service(kube, "../deploy/sc4snmp/mongo-service.yaml")


@pytest.fixture
def scheduler_config(kube):
    cm = kube.load_configmap("../deploy/sc4snmp/scheduler-config.yaml")
    cm.create()
    cm.wait_until_ready()
    cm.refresh()
    return cm


def test_poller_integration(
    rabbitmq_deployment,
    rabbitmq_service,
    mongo_deployment,
    mongo_service,
    scheduler_config,
):
    logger.info("Poller integration started Kubernetes's deployment")
    rq_deployment_pods = rabbitmq_deployment.get_pods()
    assert len(rq_deployment_pods) == 1
    rq_deployment_service = rabbitmq_service.get_endpoints()
    assert len(rq_deployment_service) == 1
    mongo_deployment_pods = mongo_deployment.get_pods()
    assert len(mongo_deployment_pods) == 1
    mongo_deployment_service = mongo_service.get_endpoints()
    assert len(mongo_deployment_service) == 1
    assert scheduler_config.obj.data["inventory.csv"] is not None
    assert scheduler_config.obj.data["config.yaml"] is not None
