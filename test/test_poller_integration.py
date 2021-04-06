import pytest

from test.kubetest_utils import (
    create_service,
    create_deployment,
    create_kubernetes_secret,
    extract_splunk_password_from_deployment,
)

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
    return "~/.microk8s/config"


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
def mib_service(kube):
    return create_service(kube, "../deploy/sc4snmp/mib-server-service.yaml")


@pytest.fixture
def mib_deployment(kube):
    return create_deployment(kube, "../deploy/sc4snmp/mib-server-deployment.yaml")


@pytest.fixture
def scheduler_deployment(kube):
    return create_deployment(kube, "../deploy/sc4snmp/scheduler-deployment.yaml")


@pytest.fixture
def worker_deployment(kube):
    return create_deployment(kube, "../deploy/sc4snmp/worker-deployment.yaml")


@pytest.fixture
def scheduler_config(kube):
    cm = kube.load_configmap("../deploy/sc4snmp/scheduler-config.yaml")
    cm.create()
    cm.wait_until_ready()
    cm.refresh()
    return cm


@pytest.fixture
def snmp_simulator_deployment(kube):
    return create_deployment(kube, "./snmp-sim-deployment.yaml")


@pytest.fixture
def snmp_simulator_service(kube):
    return create_service(kube, "./snmp-sim-service.yaml")


def test_deploy_splunk(kube):
    splunk_deployment = create_deployment(kube, "./splunk-deployment.yaml")
    password = extract_splunk_password_from_deployment(splunk_deployment)
    logger.info(f"Using the following password = {password}")


def test_poller_integration(
    rabbitmq_deployment,
    rabbitmq_service,
    mongo_deployment,
    mongo_service,
    scheduler_config,
    scheduler_deployment,
    mib_deployment,
    mib_service,
    worker_deployment,
    snmp_simulator_deployment,
    snmp_simulator_service,
):
    # In case you need to check what kubetest returns, you can see the documentation
    # of all the kubernetes python classes in here:
    # https://github.com/kubernetes-client/python/tree/master/kubernetes/docs
    logger.info("Poller integration started Kubernetes's deployment")
    rq_deployment_pods = rabbitmq_deployment.get_pods()
    assert len(rq_deployment_pods) == 1
    rq_deployment_service = rabbitmq_service.get_endpoints()
    assert len(rq_deployment_service) == 1
    mongo_deployment_pods = mongo_deployment.get_pods()
    assert len(mongo_deployment_pods) == 1
    mongo_deployment_service = mongo_service.get_endpoints()
    # logger.info(f"Endpoints: {mongo_deployment_service}")
    assert len(mongo_deployment_service) == 1
    assert scheduler_config.obj.data["inventory.csv"] is not None
    assert scheduler_config.obj.data["config.yaml"] is not None

    mib_server_service = mib_service.get_endpoints()
    mib_server_ip = mib_server_service[0].subsets[0].addresses[0].ip
    mib_server_port = mib_server_service[0].subsets[0].ports[0].port
    assert mib_server_port == 5000
    logger.info(f"MIB-server ports: {mib_server_ip}:{mib_server_port}")

    simulator_deployment_pods = snmp_simulator_deployment.get_pods()
    assert len(simulator_deployment_pods) == 1
    simulator_service_endpoints = snmp_simulator_service.get_endpoints()
    assert len(simulator_service_endpoints) == 1

    # import time
    # time.sleep(60)
    # env = worker_deployment.get_pods()[0].get_containers()[0].get_logs()
    # logger.info(f"Worker = {env}")
    secret_create, secret_yaml = create_kubernetes_secret(
        "remote-splunk", "http://localhost:8088", "12345"
    )
    assert secret_create
