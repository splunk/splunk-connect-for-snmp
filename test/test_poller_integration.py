import pytest


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
    rabbitmq_deployment_yaml = "../deploy/sc4snmp/rq-deployment.yaml"
    rq_deployment = kube.load_deployment(rabbitmq_deployment_yaml)
    rq_deployment.create()
    rq_deployment.wait_until_ready()
    rq_deployment.refresh()
    return rq_deployment


@pytest.fixture
def rabbitmq_service(kube):
    rabbitmq_service_yaml = "../deploy/sc4snmp/rq-service.yaml"
    rq_service = kube.load_service(rabbitmq_service_yaml)
    rq_service.create()
    rq_service.wait_until_ready()
    rq_service.refresh()
    return rq_service


def test_poller_integration(rabbitmq_deployment, rabbitmq_service):
    rq_deployment_pods = rabbitmq_deployment.get_pods()
    assert len(rq_deployment_pods) == 1
    rq_deployment_service = rabbitmq_service.get_endpoints()
    assert len(rq_deployment_service) == 1
