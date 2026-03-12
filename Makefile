# ============================================
# Shell
# ============================================

SHELL := /bin/bash

# ============================================
# Paths
# ============================================

MICROK8S_SCRIPT = integration_tests/scripts/run_local_microk8s_tests.sh
DOCKER_SCRIPT   = integration_tests/scripts/run_local_docker_tests.sh


# ============================================
# Helm Render
# ============================================

.PHONY: render
render:
	rm -rf rendered/manifests
	helm template -n default --values rendered/values.yaml --output-dir rendered/manifests/tests charts/splunk-connect-for-snmp
	rm -rf rendered/manifests/tests/splunk-connect-for-snmp/charts
	./render_manifests.sh


# ============================================
# Docker Integration Tests
# ============================================

.PHONY: test-docker-traps
test-docker-traps:
	bash $(DOCKER_SCRIPT) --clean --test traps

.PHONY: test-docker-poller
test-docker-poller:
	bash $(DOCKER_SCRIPT) --clean --test poller

.PHONY: test-docker-all
test-docker-all:
	bash $(DOCKER_SCRIPT) --clean --test all


# ============================================
# MicroK8s Integration Tests
# ============================================

.PHONY: test-k8s-traps
test-k8s-traps:
	bash $(MICROK8S_SCRIPT) --clean --test traps

.PHONY: test-k8s-poller
test-k8s-poller:
	bash $(MICROK8S_SCRIPT) --clean --test poller

.PHONY: test-k8s-all
test-k8s-all:
	bash $(MICROK8S_SCRIPT) --clean --test all


# ============================================
# Utilities
# ============================================

.PHONY: prepare-env
prepare-env:
	chmod +x integration_tests/scripts/*.sh

.PHONY: clean
clean:
	rm -rf rendered/manifests
	rm -rf __pycache__
	rm -rf .pytest_cache


# ============================================
# Help
# ============================================

.PHONY: help
help:
	@echo ""
	@echo "======================================"
	@echo " SC4SNMP Local Development Commands"
	@echo "======================================"
	@echo ""
	@echo "Helm:"
	@echo "  make render                     Render Helm manifests"
	@echo ""
	@echo "Docker Integration Tests:"
	@echo "  make test-docker-traps          Run trap tests"
	@echo "  make test-docker-poller         Run poller tests"
	@echo "  make test-docker-all            Run all docker tests"
	@echo ""
	@echo "MicroK8s Integration Tests:"
	@echo "  make test-k8s-traps             Run trap tests"
	@echo "  make test-k8s-poller            Run poller tests"
	@echo "  make test-k8s-all               Run all k8s tests"
	@echo ""
	@echo "Utilities:"
	@echo "  make prepare-env                Make scripts executable"
	@echo "  make clean                      Cleanup build artifacts"
	@echo ""