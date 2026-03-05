#!/bin/bash
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Color
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYELLOW='\033[1;33m'
NC='\033[0m'

step()  { echo -e "\n${CYELLOW}====== $* ======${NC}"; }
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }

function red    { printf "${RED}$@${NC}\n"; }
function green  { printf "${GREEN}$@${NC}\n"; }
function yellow { printf "${YELLOW}$@${NC}\n"; }


# ===== CHECK DOCKER =====
if ! command -v docker &> /dev/null; then
 # Remove the Ubuntu package version
  sudo apt-get remove -y docker.io docker-compose 2>/dev/null || true

  # Install Docker's official repo
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] \
    https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

  sudo apt-get update

  # Check available versions
  apt-cache madison docker-ce | grep "29.2.1"

  # Install exact version
  sudo apt-get install -y \
    docker-ce=5:29.2.1-1~ubuntu.22.04~jammy \
    docker-ce-cli=5:29.2.1-1~ubuntu.22.04~jammy \
    containerd.io

  # Verify
  if ! sudo systemctl is-active --quiet docker; then
    echo "Starting Docker daemon..."
    sudo systemctl start docker
  fi

fi

# ===== DEFAULTS =====
SPLUNK_HOST="localhost"
SPLUNK_PASSWORD="ch@ngeme!"
SPLUNK_PORT="8089"
SPLUNK_USER="admin"
SPLUNK_API="https://${SPLUNK_HOST}:${SPLUNK_PORT}"
CLEAN_INDEXES=false
TEST_FILTER="tests/"
CLEAN=false


# ===== ARG PARSING =====
while [[ $# -gt 0 ]]; do
  case "$1" in
    --password)
      SPLUNK_PASSWORD="$2"
      shift 2
      ;;

    --host)
      SPLUNK_HOST="$2"
      SPLUNK_API="https://${SPLUNK_HOST}:${SPLUNK_PORT}"
      shift 2
      ;;

    --clean)
      CLEAN=true
      CLEAN_INDEXES=true
      shift
      ;;

    --test)

      if [[ -z "${2:-}" ]]; then
        error "--test requires argument: traps | poller | all"
        exit 1
      fi

      case "$2" in
        traps)
          TEST_FILTER="tests/test_trap_integration.py"
          ;;
        poller)
          TEST_FILTER="tests/test_poller_integration.py"
          ;;
        all)
          TEST_FILTER="tests/"
          ;;
        *)
          error "Invalid test type: $2 (allowed: traps | poller | all)"
          exit 1
          ;;
      esac

      shift 2
      ;;

    *)
      error "Unknown argument: $1"
      exit 1
      ;;
  esac
done

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

  # Delete PVCs
  sudo microk8s kubectl delete pvc --all -n sc4snmp 2>/dev/null || true

  # Delete the secret so re-creation doesn't fail
  sudo microk8s kubectl delete secret sv3poller -n sc4snmp 2>/dev/null || true

  info "K8s cleanup complete "
}

wait_for_splunk() {
  while [ "$(sudo docker ps | grep "splunk:latest" | grep healthy)" == "" ]; do
    echo $(yellow "Waiting for Splunk initialization")
    sleep 1
  done
}

define_python() {
  echo $(yellow "define python")
  if command -v python &>/dev/null; then
    PYTHON=python
  elif command -v python3 &>/dev/null; then
    PYTHON=python3
  else
    echo $(red "Cannot find python command")
    exit 1
  fi
}
deploy_poetry() {

  step "Installing Poetry and Python dependencies"

  sudo apt-get update -y
  sudo apt-get install -y python3-venv python3-pip curl

  # Install Poetry only if not already installed
  if ! command -v poetry >/dev/null 2>&1; then
      info "Installing Poetry..."
      curl -sSL https://install.python-poetry.org | $PYTHON -
  else
      info "Poetry already installed"
  fi

  # Fix PATH for current user (works for any username)
  export PATH="$HOME/.local/bin:$PATH"
  hash -r

  # Verify Poetry installation
  poetry --version || { error "Poetry installation failed"; exit 1; }

  step "Installing project dependencies"

  poetry install

  poetry add --group dev splunk-sdk splunklib pysnmplib || true
}


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

start_splunk() {
  step "STEP 3: START SPLUNK"
  if sudo lsof -i :8000 >/dev/null 2>&1; then
    info "External Splunk detected on port 8000 "
  else
    info "Starting Splunk in Docker..."
    mkdir -p "$PWD/splunk-data"
    sudo docker run -d \
      -p 8000:8000 \
      -p 8088:8088 \
      -p 8089:8089 \
      -e SPLUNK_GENERAL_TERMS="--accept-sgt-current-at-splunk-com" \
      -e SPLUNK_START_ARGS="--accept-license" \
      -e SPLUNK_PASSWORD="changeme2" \
      -v "$PWD/splunk-data:/opt/splunk/var" \
      splunk/splunk:latest
  fi
}

check_splunk() {
  step "Checking Splunk connection"
  if curl -sk -u "${SPLUNK_USER}:${SPLUNK_PASSWORD}" \
    "${SPLUNK_API}/services/server/info" | grep -q "build"; then
    info "Splunk reachable at ${SPLUNK_HOST}:${SPLUNK_PORT} "
  else
    error "Cannot connect to Splunk at ${SPLUNK_API}"
    exit 1
  fi
}

create_indexes() {
  step "Creating Splunk indexes"
  declare -A INDEXES=(
    [netmetrics]="metric"
    [em_metrics]="metric"
    [netops]="event"
    [em_events]="event"
    [em_meta]="event"
  )
  for name in "${!INDEXES[@]}"; do
    dtype="${INDEXES[$name]}"
    code=$(curl -sk -o /dev/null -w "%{http_code}" \
      -u "${SPLUNK_USER}:${SPLUNK_PASSWORD}" \
      "${SPLUNK_API}/services/data/indexes" \
      -d "name=${name}" -d "datatype=${dtype}")
    case "$code" in
      201) info "Created index: $name ($dtype)" ;;
      409) info "Index already exists: $name — OK" ;;
      *)   warn "Unexpected HTTP $code for index: $name" ;;
    esac
  done
}

get_hec_token() {
  local token response
  response=$(curl -sk -u "${SPLUNK_USER}:${SPLUNK_PASSWORD}" \
    "${SPLUNK_API}/servicesNS/admin/splunk_httpinput/data/inputs/http" \
    -d "name=sc4snmp_test_token" \
    -d "index=em_events" \
    -d "indexes=em_events,em_metrics,em_meta,netmetrics,netops")
  token=$(echo "$response" | grep -oP '(?<=<s:key name="token">)[^<]+' | head -1)
  if [[ -z "$token" ]]; then
    token=$(curl -sk -u "${SPLUNK_USER}:${SPLUNK_PASSWORD}" \
      "${SPLUNK_API}/servicesNS/admin/splunk_httpinput/data/inputs/http/sc4snmp_test_token" \
      | grep -oP '(?<=<s:key name="token">)[^<]+' | head -1)
  fi
  if [[ -z "$token" ]]; then
    echo "ERROR: Could not get HEC token" >&2
    exit 1
  fi
  echo "$token"
}

clean_indexes() {
  step "Cleaning indexes"
  for idx in em_metrics em_events em_meta netmetrics netops; do
    curl -sk -u "${SPLUNK_USER}:${SPLUNK_PASSWORD}" \
      -X DELETE "${SPLUNK_API}/services/data/indexes/$idx" >/dev/null || true
  done
  sleep 10
  create_indexes
}

start_snmpsim() {
  echo "Starting SNMP simulators..."

  sudo docker rm -f $(sudo docker ps -aq --filter ancestor=tandrup/snmpsim) 2>/dev/null || true

  # Main simulator required by SC4SNMP
  sudo docker run -d \
    --name snmp-sim-161 \
    -p 161:161/udp \
    tandrup/snmpsim >/dev/null

  echo "Main simulator started on 161 "

  for port in 1162 1163 1164 1165; do
    if ! sudo lsof -i :$port >/dev/null 2>&1; then
      sudo docker run -d -p ${port}:161/udp tandrup/snmpsim >/dev/null
      echo "Started simulator on $port "
    else
      echo "Port $port already in use, skipping"
    fi
  done

  if ! sudo lsof -i :1166 >/dev/null 2>&1; then
    sudo docker run -d -p 1166:161/udp \
      -v "$(pwd)/snmpsim/data:/usr/local/snmpsim/data" \
      -e "EXTRA_FLAGS=--variation-modules-dir=/usr/local/snmpsim/variation --data-dir=/usr/local/snmpsim/data" \
      tandrup/snmpsim >/dev/null

    echo "Custom simulator started on 1166 "
  fi

  sleep 3

  if snmpwalk -v2c -c public 127.0.0.1 >/dev/null 2>&1; then
    echo "SNMP simulator verified "
  else
    echo "WARNING: SNMP simulator not responding"
  fi
}

# ===== RUN TESTS =====
run_tests() {

  step "Waiting for first poll cycle (up to 3 minutes)"

  local waited=0

  while [[ $waited -lt 180 ]]; do

    count=$(curl -sk -u "${SPLUNK_USER}:${SPLUNK_PASSWORD}" \
      "${SPLUNK_API}/services/search/jobs" \
      -d "search=search index=netops sourcetype=\"sc4snmp:event\" earliest=-10m" \
      -d exec_mode=oneshot 2>/dev/null \
      | grep -c "<s:key name=\"count\">" || echo 0)

    if [[ "$count" -gt 0 ]]; then
      info "Data confirmed in Splunk after ${waited}s "
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

# Clean K8s before doing anything if --clean was passed
[[ "$CLEAN" == true ]] && clean_k8s

pwd

echo $(green "Building Docker image")
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

echo $(green "Installing SC4SNMP on Kubernetes")

# Ensure namespace exists
sudo microk8s kubectl create namespace sc4snmp --dry-run=client -o yaml | sudo microk8s kubectl apply -f -

# Create SNMPv3 secret
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

# Install SC4SNMP
sudo microk8s helm3 upgrade --install snmp \
  -f values.yaml \
  ../charts/splunk-connect-for-snmp \
  --namespace=sc4snmp \
  --create-namespace

wait_for_pod_initialization || true
wait_for_sc4snmp_pods_to_be_up || true
check_metallb_status || true

echo "👉 Starting Python setup..."
define_python
deploy_poetry ||true
sleep 10
run_tests

# Cleanup and restore values.yaml
info "Restoring values.yaml"

sed -i "s|${token}|###SPLUNK_TOKEN###|g" "$VALUES_FILE"
sed -i "s|${HOST_IP}|###LOAD_BALANCER_ID###|g" "$VALUES_FILE"
