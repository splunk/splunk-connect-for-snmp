#!/usr/bin/env bash
set -euo pipefail

# Color
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color
# ===== PATHS =====
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INT_TEST_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${INT_TEST_DIR}/.." && pwd)"
CHART_DIR="${REPO_ROOT}/charts/splunk-connect-for-snmp"
AUTODISCOVERY_ENABLED="${AUTODISCOVERY_ENABLED:-true}"
if [[ "$AUTODISCOVERY_ENABLED" != "true" && "$AUTODISCOVERY_ENABLED" != "false" ]]; then
  echo "AUTODISCOVERY_ENABLED must be 'true' or 'false'" >&2
  exit 2
fi

echo "SCRIPT_DIR: $SCRIPT_DIR"
echo "INT_TEST_DIR: $INT_TEST_DIR"
echo "REPO_ROOT: $REPO_ROOT"

cd "$REPO_ROOT"
function red {
    printf "${RED}$@${NC}\n"
}

function green {
    printf "${GREEN}$@${NC}\n"
}

function yellow {
    printf "${YELLOW}$@${NC}\n"
}

dump_microk8s_diagnostics() {
  echo $(green "[INFO] MicroK8s status at failure:")
  timeout 20s sudo microk8s status || true
  echo $(green "[INFO] Kubernetes nodes and pods at failure:")
  timeout 20s sudo microk8s kubectl get nodes -o wide || true
  timeout 20s sudo microk8s kubectl get pods -A -o wide || true
  timeout 20s sudo microk8s kubectl get all \
    -n microk8s-agent-simulator -o wide || true
  timeout 20s sudo microk8s kubectl get all -n sc4snmp -o wide || true
  echo $(green "[INFO] Recent Kubernetes events:")
  timeout 20s sudo microk8s kubectl get events -A \
    --sort-by=.lastTimestamp || true
  echo $(green "[INFO] Recent simulator and SC4SNMP container logs:")
  timeout 30s sudo microk8s kubectl logs -n microk8s-agent-simulator \
    -l sc4snmp.integration.autodiscovery=true \
    --all-containers=true --prefix=true --tail=50 --ignore-errors=true || true
  timeout 30s sudo microk8s kubectl logs -n sc4snmp \
    -l app.kubernetes.io/instance=snmp \
    --all-containers=true --prefix=true --tail=50 --ignore-errors=true || true
  echo $(green "[INFO] Kubelite status and recent log entries:")
  sudo systemctl status snap.microk8s.daemon-kubelite \
    --no-pager --full || true
  sudo journalctl -u snap.microk8s.daemon-kubelite \
    --no-pager -n 150 || true
}

handle_setup_error() {
  local exit_code="$1"
  local line_number="$2"

  trap - ERR
  red "[ERROR] MicroK8s integration setup failed at line ${line_number} (exit ${exit_code})."
  dump_microk8s_diagnostics
  exit "${exit_code}"
}

trap 'handle_setup_error "$?" "$LINENO"' ERR

wait_for_microk8s_api() {
  local timeout_seconds="${1:-180}"
  local deadline=$((SECONDS + timeout_seconds))
  local consecutive_successes=0
  local attempt=0

  while (( SECONDS < deadline )); do
    attempt=$((attempt + 1))
    if timeout 15s sudo microk8s kubectl get --raw=/readyz >/dev/null 2>&1; then
      consecutive_successes=$((consecutive_successes + 1))
      if (( consecutive_successes >= 5 )); then
        return 0
      fi
    else
      consecutive_successes=0
      echo $(green "[INFO] MicroK8s API is not ready (attempt ${attempt}); retrying")
    fi
    sleep 3
  done

  echo $(red "MicroK8s API did not remain ready for five consecutive checks")
  return 1
}

wait_for_splunk() {
  while [ "$(sudo docker ps | grep "splunk:latest" | grep healthy)" == "" ] ; do
    echo $(yellow "Waiting for Splunk initialization")
    sleep 1
  done
}

function define_python() {
  echo $(yellow "define python")
  if command -v python &> /dev/null; then
      PYTHON=python
  elif command -v python3 &> /dev/null; then
      PYTHON=python3
  else
    echo $(red "Cannot find python command")
    exit 1
  fi
}

deploy_poetry() {
  sudo apt -y install python3-venv
  curl -sSL https://install.python-poetry.org | $PYTHON -
  export PATH="/home/ubuntu/.local/bin:$PATH"
  poetry install
}

wait_for_pod_initialization() {
  while [ "$(sudo microk8s kubectl get pod -n sc4snmp | grep ContainerCreating)" != "" ] ; do
    echo "Waiting for POD initialization..."
    sleep 1
  done
}

check_metallb_status() {
  while [ "$(sudo microk8s kubectl get svc -n sc4snmp | grep snmp-splunk-connect-for-snmp-trap | grep "pending" )" != "" ] ; do
    echo $(green "[INFO] MetalLB service is still pending; reconfiguring the address pool")
    sudo microk8s disable metallb
    printf '%s/32\n' "$(hostname -I | cut -d " " -f1)" | \
      sudo microk8s enable metallb
    sleep 30
  done
}

wait_for_sc4snmp_pods_to_be_up() {
  while [ "$(sudo microk8s kubectl get pod -n sc4snmp | grep 0/1)" != "" ] ; do
    echo "Waiting for SC4SNMP pods initialization..."
    sleep 1
  done
}

sudo apt-get update -y
sudo apt-get install snmpd -y
sudo sed -i -E 's/agentaddress[[:space:]]+127.0.0.1,\[::1\]/#agentaddress  127.0.0.1,\[::1\]\nagentaddress udp:1161,udp6:[::1]:1161/g' /etc/snmp/snmpd.conf
echo "" | sudo tee -a /etc/snmp/snmpd.conf
echo "createUser r-wuser SHA admin1234 AES admin1234" | sudo tee -a /etc/snmp/snmpd.conf
echo "rwuser r-wuser priv" | sudo tee -a /etc/snmp/snmpd.conf
sudo systemctl restart snmpd

echo "Show working directory:"
pwd

green "[STEP] Building the SC4SNMP Docker image"

sudo docker build -t snmp-local .

sudo docker save snmp-local > myimage.tar
sudo microk8s ctr image import myimage.tar
echo $(green "[DONE] Built and imported snmp-local into MicroK8s")
mkdir -p "$PWD/splunk-data"

sudo docker pull splunk/splunk:latest
green "[STEP] Starting Splunk in Docker"
sudo docker run -d -p 8000:8000 -p 8088:8088 -p 8089:8089 -e SPLUNK_GENERAL_TERMS=--accept-sgt-current-at-splunk-com  -e SPLUNK_START_ARGS='--accept-license' -e SPLUNK_PASSWORD='changeme2' -v "$PWD/splunk-data:/opt/splunk/var" splunk/splunk:latest

wait_for_splunk
echo $(green "[DONE] Splunk container is healthy")

cd "$INT_TEST_DIR"
chmod +x "$SCRIPT_DIR/prepare_splunk.sh"
chmod +x "$SCRIPT_DIR/install_sck.sh"

"$SCRIPT_DIR/prepare_splunk.sh"
"$SCRIPT_DIR/install_sck.sh"


VALUES_FILE="$INT_TEST_DIR/values.yaml"
DISCOVERY_PATH_DIR="$INT_TEST_DIR/discovery"

sed -i "s/###SPLUNK_TOKEN###/$(cat hec_token)/" "$VALUES_FILE"
sed -i "s/###LOAD_BALANCER_ID###/$(hostname -I | cut -d " " -f1)/" "$VALUES_FILE"
sed -i "s|###DISCOVERY_PATH###|${DISCOVERY_PATH_DIR}|" "$VALUES_FILE"

sudo docker run -d -p 161:161/udp tandrup/snmpsim
sudo docker run -d -p 1162:161/udp tandrup/snmpsim
sudo docker run -d -p 1163:161/udp tandrup/snmpsim
sudo docker run -d -p 1164:161/udp tandrup/snmpsim
sudo docker run -d -p 1165:161/udp tandrup/snmpsim
sudo docker run -d -p 1166:161/udp -v $(pwd)/snmpsim/data:/usr/local/snmpsim/data -e EXTRA_FLAGS="--variation-modules-dir=/usr/local/snmpsim/variation --data-dir=/usr/local/snmpsim/data" tandrup/snmpsim

green "[STEP] Enabling required MicroK8s add-ons"
sudo microk8s enable helm3
sudo microk8s enable hostpath-storage
sudo microk8s enable dns
sudo microk8s enable rbac
sudo microk8s enable community
sudo microk8s enable metrics-server
sudo systemctl enable iscsid
printf '%s/32\n' "$(hostname -I | cut -d " " -f1)" | \
  sudo microk8s enable metallb
sudo microk8s status --wait-ready
echo $(green "[DONE] MicroK8s add-ons are enabled")

green "[STEP] Waiting for a stable MicroK8s API"
if ! wait_for_microk8s_api 90; then
  echo $(green "[INFO] MicroK8s did not stabilize after add-on installation; restarting it once")
  sudo snap restart microk8s
  sudo microk8s status --wait-ready
  wait_for_microk8s_api 180
fi
echo $(green "[DONE] MicroK8s API passed five consecutive readiness checks")

if [[ "$AUTODISCOVERY_ENABLED" == "true" ]]; then
  green "[STEP] Running setup_autodiscovery_simulators.sh with the MicroK8s backend"
  if "$SCRIPT_DIR/setup_autodiscovery_simulators.sh" microk8s; then
    echo $(green "[DONE] setup_autodiscovery_simulators.sh completed successfully")
  else
    simulator_setup_exit=$?
    if timeout 15s sudo microk8s kubectl get --raw=/readyz >/dev/null 2>&1; then
      echo $(red "Autodiscovery simulator setup failed while the MicroK8s API remained healthy")
      exit "${simulator_setup_exit}"
    fi

    echo $(green "[INFO] The MicroK8s API stopped during simulator deployment; restarting it once")
    sudo snap restart microk8s
    sudo microk8s status --wait-ready
    wait_for_microk8s_api 180
    echo $(green "[INFO] Running setup_autodiscovery_simulators.sh again after MicroK8s recovery")
    "$SCRIPT_DIR/setup_autodiscovery_simulators.sh" microk8s
    echo $(green "[DONE] setup_autodiscovery_simulators.sh completed after MicroK8s recovery")
  fi
else
  echo $(green "[INFO] Skipping autodiscovery simulators for this test part")
fi


cd "$CHART_DIR"
sudo microk8s helm3 dep update
cd "$INT_TEST_DIR"

green "[STEP] Installing SC4SNMP on Kubernetes"

sudo microk8s kubectl create namespace sc4snmp --dry-run=client -o yaml | sudo microk8s kubectl apply -f -
sudo microk8s kubectl create -n sc4snmp secret generic sv3poller --dry-run=client -o yaml --from-literal=userName=r-wuser --from-literal=authKey=admin1234 --from-literal=privKey=admin1234 --from-literal=authProtocol=SHA --from-literal=privProtocol=AES --from-literal=securityEngineId=8000000903000A397056B8AC | sudo microk8s kubectl apply -f -
HELM_DISCOVERY_ARGS=()
if [[ "$AUTODISCOVERY_ENABLED" == "true" ]]; then
  sudo microk8s kubectl create -n sc4snmp secret generic autodiscovery-v3-sha-aes --dry-run=client -o yaml --from-literal=userName=autodiscovery-sha --from-literal=authKey=AuthPass1 --from-literal=privKey=PrivPass1 --from-literal=authProtocol=SHA --from-literal=privProtocol=AES --from-literal=securityEngineId=8000000903000A3900000101 | sudo microk8s kubectl apply -f -
else
  HELM_DISCOVERY_ARGS+=(--set discovery.enabled=false)
fi

sudo microk8s helm3 install snmp -f values.yaml ../charts/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace "${HELM_DISCOVERY_ARGS[@]}"

wait_for_pod_initialization
wait_for_sc4snmp_pods_to_be_up
check_metallb_status
echo $(green "[DONE] SC4SNMP pods and load-balancer service are ready")

if [[ ${1:-} == 'integration' ]]; then
  define_python
  deploy_poetry
fi
