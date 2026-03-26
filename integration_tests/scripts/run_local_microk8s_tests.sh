#!/bin/bash
set -eo pipefail

# ===== LOAD SHARED HELPERS =====
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

install_docker
parse_common_args "$@"

# ===== CLEAN K8s RESOURCES =====
clean_k8s() {
  step "Cleaning K8s SC4SNMP resources"

  if sudo microk8s helm3 status snmp -n sc4snmp &>/dev/null; then
    info "Uninstalling Helm release 'snmp'..."
    sudo microk8s helm3 uninstall snmp -n sc4snmp || true
    sleep 5
  else
    info "No existing Helm release 'snmp' found — skipping"
  fi

  sudo microk8s kubectl delete pvc --all -n sc4snmp 2>/dev/null || true
  sudo microk8s kubectl delete secret sv3poller -n sc4snmp 2>/dev/null || true

  info "K8s cleanup complete"
}

# ===== K8S WAIT HELPERS =====
wait_for_pod_initialization() {
  while [ "$(sudo microk8s kubectl get pod -n sc4snmp | grep ContainerCreating)" != "" ]; do
    echo "Waiting for POD initialization..."
    sleep 1
  done
}

check_metallb_status() {
  while [ "$(sudo microk8s kubectl get svc -n sc4snmp | grep snmp-splunk-connect-for-snmp-trap | grep "pending")" != "" ]; do
    echo "MetalLB was enabled unsuccessfully"
    sudo microk8s disable metallb
    yes $(hostname -I | cut -d " " -f1)/32 | sudo microk8s enable metallb
    sleep 30
  done
}

wait_for_sc4snmp_pods_to_be_up() {
  while [ "$(sudo microk8s kubectl get pod -n sc4snmp | grep 0/1)" != "" ]; do
    echo "Waiting for SC4SNMP pods initialization..."
    sleep 1
  done
}

# ===== START SNMP SIMULATORS =====
start_snmpsim() {
  echo "Starting SNMP simulators..."

  sudo docker rm -f $(sudo docker ps -aq --filter ancestor=tandrup/snmpsim) 2>/dev/null || true

  sudo docker run -d \
    --name snmp-sim-161 \
    -p 161:161/udp \
    tandrup/snmpsim >/dev/null

  echo "Main simulator started on 161"

  for port in 1162 1163 1164 1165; do
    if ! sudo lsof -i :$port >/dev/null 2>&1; then
      sudo docker run -d -p ${port}:161/udp tandrup/snmpsim >/dev/null
      echo "Started simulator on $port"
    else
      echo "Port $port already in use, skipping"
    fi
  done

  if ! sudo lsof -i :1166 >/dev/null 2>&1; then
    sudo docker run -d -p 1166:161/udp \
      -v "$(pwd)/snmpsim/data:/usr/local/snmpsim/data" \
      -e "EXTRA_FLAGS=--variation-modules-dir=/usr/local/snmpsim/variation --data-dir=/usr/local/snmpsim/data" \
      tandrup/snmpsim >/dev/null

    echo "Custom simulator started on 1166"
  fi

  sleep 3

  if snmpwalk -v2c -c public 127.0.0.1 >/dev/null 2>&1; then
    echo "SNMP simulator verified"
  else
    echo "WARNING: SNMP simulator not responding"
  fi
}

# ===== RUN TESTS =====
run_tests() {
  step "Waiting for first poll cycle (up to 3 minutes)"

  local waited=0

  while [[ $waited -lt 180 ]]; do
    local count
    count=$(curl -sk -u "${SPLUNK_USER}:${SPLUNK_PASSWORD}" \
      "${SPLUNK_API}/services/search/jobs" \
      -d "search=search index=netops sourcetype=\"sc4snmp:event\" earliest=-10m" \
      -d exec_mode=oneshot 2>/dev/null \
      | grep -c "<s:key name=\"count\">" || true)

    if [[ "$count" -gt 0 ]]; then
      info "Data confirmed in Splunk after ${waited}s"
      break
    fi

    info "No data yet... ${waited}s elapsed"

    sleep 20
    (( waited += 20 ))
  done

  [[ $waited -ge 180 ]] && warn "Timeout waiting for data — running tests anyway"

  step "Running Integration Tests"

  local trap_ip
  trap_ip="$(hostname -I | cut -d " " -f1)"
  info "Using trap_external_ip: $trap_ip"
  info "Running filter: ${TEST_FILTER}"

  cd "${INT_TEST_DIR}"
  poetry run pytest \
    --splunk_host="${SPLUNK_HOST}" \
    --splunk_port="${SPLUNK_PORT}" \
    --splunk_user="${SPLUNK_USER}" \
    --splunk_password="${SPLUNK_PASSWORD}" \
    --trap_external_ip="${trap_ip}" \
    --sc4snmp_deployment="microk8s" \
    -v \
    ${TEST_FILTER}
}

# ===== MAIN =====

[[ "$CLEAN" == true ]] && clean_k8s

pwd

echo "$(green "Building Docker image")"
sudo docker build --no-cache -t snmp-local:latest .

sudo docker save snmp-local:latest > snmp-local.tar

# ===== CHECK MICROK8S =====
if ! command -v microk8s &> /dev/null; then
  info "Installing MicroK8s..."
  sudo snap install microk8s --classic
  sudo usermod -aG microk8s $USER
  newgrp microk8s
  sleep 20
fi
sudo microk8s status --wait-ready

sudo microk8s ctr image import snmp-local.tar
mkdir -p "$PWD/splunk-data"

start_splunk
check_splunk
create_indexes
[[ "$CLEAN_INDEXES" == true ]] && clean_indexes

token=$(get_hec_token)

sudo microk8s helm3 repo add splunk-otel-collector-chart https://signalfx.github.io/splunk-otel-collector-chart
sudo microk8s helm3 upgrade --install sck \
  --set="clusterName=my-cluster" \
  --set="splunkPlatform.endpoint=https://$(hostname -I | cut -d " " -f1):8088/services/collector" \
  --set="splunkPlatform.insecureSkipVerify=true" \
  --set="splunkPlatform.token=${token}" \
  --set="splunkPlatform.metricsEnabled=true" \
  --set="splunkPlatform.metricsIndex=em_metrics" \
  --set="splunkPlatform.index=em_logs" \
  splunk-otel-collector-chart/splunk-otel-collector

VALUES_FILE="${SCRIPT_DIR}/../values.yaml"

HOST_IP=$(hostname -I | awk '{print $1}')

info "Updating values.yaml"

sed -i "s|###SPLUNK_TOKEN###|${token}|g" "$VALUES_FILE"
sed -i "s|###LOAD_BALANCER_ID###|${HOST_IP}|g" "$VALUES_FILE"

info "Using Host IP: $HOST_IP"

LOCAL_RUN=true
if [[ "$LOCAL_RUN" == "true" ]]; then
  echo "Using root user for local Kubernetes"
  sed -i '/securityContext:/,/runAsGroup:/d' "$VALUES_FILE"
fi

start_snmpsim

step "MicroK8s Setup"

# ===== CHECK MICROK8S =====
if ! command -v microk8s &> /dev/null; then
  info "Installing MicroK8s..."
  sudo snap install microk8s --classic
  sudo usermod -aG microk8s $USER
  newgrp microk8s
  sleep 10
fi

HOST_IP=$(hostname -I | awk '{print $1}')
RANGE="${HOST_IP%.*}.240-${HOST_IP%.*}.250"
info "MetalLB range: $RANGE"

sudo microk8s enable dns || true
sudo microk8s enable hostpath-storage || true
sudo microk8s enable helm3 || true
sudo microk8s enable rbac || true
sudo microk8s enable metrics-server || true
yes "$RANGE" | sudo microk8s enable metallb || true
sudo microk8s status --wait-ready

CHART_DIR="${SCRIPT_DIR}/../../charts/splunk-connect-for-snmp"
cd "$CHART_DIR"
sudo microk8s helm3 dep update
cd ../../integration_tests

echo "$(green "Installing SC4SNMP on Kubernetes")"

sudo microk8s kubectl create namespace sc4snmp --dry-run=client -o yaml | sudo microk8s kubectl apply -f -

sudo microk8s kubectl apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: sv3poller
  namespace: sc4snmp
type: Opaque
stringData:
  userName: r-wuser
  authKey: admin1234
  privKey: admin1234
  authProtocol: SHA
  privProtocol: AES
  securityEngineId: "8000000903000A397056B8AC"
EOF

sudo microk8s helm3 upgrade --install snmp \
  -f values.yaml \
  ../charts/splunk-connect-for-snmp \
  --namespace=sc4snmp \
  --create-namespace

wait_for_pod_initialization || true
wait_for_sc4snmp_pods_to_be_up || true
check_metallb_status || true

echo "Starting Python setup..."
ensure_python
deploy_poetry || true
sleep 10
run_tests

info "Restoring values.yaml"

sed -i "s|${token}|###SPLUNK_TOKEN###|g" "$VALUES_FILE"
sed -i "s|${HOST_IP}|###LOAD_BALANCER_ID###|g" "$VALUES_FILE"
