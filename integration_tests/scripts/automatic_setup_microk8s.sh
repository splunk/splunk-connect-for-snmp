#!/bin/bash

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
    echo "MetalLB was enabled unsuccessfully"
    sudo microk8s disable metallb
    yes $(hostname -I | cut -d " " -f1)/32 | sudo microk8s enable metallb
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

echo $(green "Building Docker image")

sudo docker build -t snmp-local .

sudo docker save snmp-local > myimage.tar
sudo microk8s ctr image import myimage.tar
mkdir -p "$PWD/splunk-data"

sudo docker pull splunk/splunk:latest
echo $(green "Running Splunk in Docker")
sudo docker run -d -p 8000:8000 -p 8088:8088 -p 8089:8089 -e SPLUNK_GENERAL_TERMS=--accept-sgt-current-at-splunk-com  -e SPLUNK_START_ARGS='--accept-license' -e SPLUNK_PASSWORD='changeme2' -v "$PWD/splunk-data:/opt/splunk/var" splunk/splunk:latest

wait_for_splunk

cd "$INT_TEST_DIR"
chmod +x "$SCRIPT_DIR/prepare_splunk.sh"
chmod +x "$SCRIPT_DIR/install_sck.sh"

"$SCRIPT_DIR/prepare_splunk.sh"
"$SCRIPT_DIR/install_sck.sh"


VALUES_FILE="$INT_TEST_DIR/values.yaml"

sed -i "s/###SPLUNK_TOKEN###/$(cat hec_token)/" "$VALUES_FILE"
sed -i "s/###LOAD_BALANCER_ID###/$(hostname -I | cut -d " " -f1)/" "$VALUES_FILE"

sudo docker run -d -p 161:161/udp tandrup/snmpsim
sudo docker run -d -p 1162:161/udp tandrup/snmpsim
sudo docker run -d -p 1163:161/udp tandrup/snmpsim
sudo docker run -d -p 1164:161/udp tandrup/snmpsim
sudo docker run -d -p 1165:161/udp tandrup/snmpsim
sudo docker run -d -p 1166:161/udp -v $(pwd)/snmpsim/data:/usr/local/snmpsim/data -e EXTRA_FLAGS="--variation-modules-dir=/usr/local/snmpsim/variation --data-dir=/usr/local/snmpsim/data" tandrup/snmpsim

sudo microk8s enable helm3
sudo microk8s enable hostpath-storage
sudo microk8s enable dns
sudo microk8s enable rbac
sudo microk8s enable community
sudo microk8s enable metrics-server
sudo systemctl enable iscsid
yes $(hostname -I | cut -d " " -f1)/32 | sudo microk8s enable metallb
sudo microk8s status --wait-ready


cd "$CHART_DIR"
sudo microk8s helm3 dep update
cd "$INT_TEST_DIR"

echo $(green "Installing SC4SNMP on Kubernetes")

sudo microk8s helm3 install snmp -f values.yaml ../charts/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
sudo microk8s kubectl create -n sc4snmp secret generic sv3poller --from-literal=userName=r-wuser --from-literal=authKey=admin1234 --from-literal=privKey=admin1234 --from-literal=authProtocol=SHA --from-literal=privProtocol=AES --from-literal=securityEngineId=8000000903000A397056B8AC

wait_for_pod_initialization
wait_for_sc4snmp_pods_to_be_up
check_metallb_status

if [[ $1 == 'integration' ]]; then
  define_python
  deploy_poetry
fi
