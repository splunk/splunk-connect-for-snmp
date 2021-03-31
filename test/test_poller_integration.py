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


def test_poller_integration(kube):
    pass
