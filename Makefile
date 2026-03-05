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

.PHONY: docker-traps
docker-traps:
	bash $(DOCKER_SCRIPT) --clean --test traps

.PHONY: docker-poller
docker-poller:
	bash $(DOCKER_SCRIPT) --clean --test poller

.PHONY: docker-all
docker-all:
	bash $(DOCKER_SCRIPT) --clean --test all


# ============================================
# MicroK8s Integration Tests
# ============================================

.PHONY: k8s-traps
k8s-traps:
	bash $(MICROK8S_SCRIPT) --clean --test traps

.PHONY: k8s-poller
k8s-poller:
	bash $(MICROK8S_SCRIPT) --clean --test poller

.PHONY: k8s-all
k8s-all:
	bash $(MICROK8S_SCRIPT) --clean --test all


# ============================================
# Utilities
# ============================================

.PHONY: setup
setup:
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
	@echo "  make docker-traps               Run trap tests "
	@echo "  make docker-poller              Run poller tests "
	@echo "  make docker-all                 Run all docker tests"
	@echo ""
	@echo "MicroK8s Integration Tests:"
	@echo "  make k8s-traps                  Run trap tests"
	@echo "  make k8s-poller                 Run poller tests"
	@echo "  make k8s-all                    Run all k8s tests"
	@echo ""
	@echo "Utilities:"
	@echo "  make setup                      Make scripts executable"
	@echo "  make clean                      Cleanup build artifacts"
	@echo ""