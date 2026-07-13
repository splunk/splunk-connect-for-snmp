
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
CONFIG_DIR="${INT_TEST_DIR}/configs"
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

wait_for_containers_to_be_up() {
  while true; do
    CONTAINERS_SC4SNMP=$(sudo docker ps | grep "sc4snmp\|worker-poller\|worker-sender\|worker-trap" | grep -v "Name" | wc -l)
    if [ "$CONTAINERS_SC4SNMP" -gt 0 ]; then
      CONTAINERS_UP=$(sudo docker ps | grep "sc4snmp\|worker-poller\|worker-sender\|worker-trap" | grep "Up" | wc -l)
      CONTAINERS_EXITED=$(sudo docker ps | grep "sc4snmp\|worker-poller\|worker-sender\|worker-trap" | grep "Exited" | wc -l)
      CONTAINERS_TOTAL=$CONTAINERS_SC4SNMP

      if [ "$CONTAINERS_UP" -eq "$CONTAINERS_TOTAL" ] || \
         { [ "$CONTAINERS_EXITED" -eq 1 ] && [ "$((CONTAINERS_UP + CONTAINERS_EXITED))" -eq "$CONTAINERS_TOTAL" ]; }; then
        echo $(green "All 'sc4snmp' containers are ready.")
        break
      fi

      echo $(yellow "Waiting for all 'sc4snmp' containers to be ready...")
    else
      echo $(yellow "No 'sc4snmp' containers found. Waiting for them to appear...")
    fi

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

sudo docker pull splunk/splunk:latest
echo $(green "Running Splunk in Docker")
sudo docker run -d -p 8000:8000 -p 8088:8088 -p 8089:8089 -e SPLUNK_GENERAL_TERMS=--accept-sgt-current-at-splunk-com -e SPLUNK_START_ARGS='--accept-license' -e SPLUNK_PASSWORD='changeme2' splunk/splunk:latest

wait_for_splunk

cd "$INT_TEST_DIR"


chmod u+x "$SCRIPT_DIR/prepare_splunk.sh"
"$SCRIPT_DIR/prepare_splunk.sh"
echo $(green "Setting up docker compose configuration")
DOCKER_COMPOSE_LOCAL="${INT_TEST_DIR}/docker_compose"
COMPOSE_FILE="${DOCKER_COMPOSE_LOCAL}/docker-compose.yaml"
ENV_FILE="${DOCKER_COMPOSE_LOCAL}/.env"
rm -rf "$DOCKER_COMPOSE_LOCAL"
cp -r "$REPO_ROOT/docker_compose" "$DOCKER_COMPOSE_LOCAL"

SECRET_FOLDER="sample_v3_values"

SCHEDULER_CONFIG_FILE="$CONFIG_DIR/scheduler-config.yaml"
TRAPS_CONFIG_FILE="$CONFIG_DIR/traps-config.yaml"
INVENTORY_FILE="$CONFIG_DIR/inventory-tests.csv"
DISCOVERY_CONFIG_FILE="$CONFIG_DIR/discovery-config-docker.yaml"
DISCOVERY_PATH_DIR="$(pwd)/discovery"

SPLUNK_HEC_HOST=$(hostname -I | cut -d " " -f1)
SPLUNK_HEC_TOKEN=$(cat hec_token)

set_var() {
  local key="$1" val="$2"
  grep -v "^${key}=" "$ENV_FILE" > "${ENV_FILE}.tmp" || true
  echo "${key}=${val}" >> "${ENV_FILE}.tmp"
  mv "${ENV_FILE}.tmp" "$ENV_FILE"
}

set_var "SC4SNMP_IMAGE"                          "snmp-local"
set_var "SC4SNMP_TAG"                            "latest"
set_var "SC4SNMP_VERSION"                        "latest"
set_var "SPLUNK_HEC_HOST"                        "$SPLUNK_HEC_HOST"
set_var "SPLUNK_HEC_TOKEN"                       "$SPLUNK_HEC_TOKEN"
set_var "SPLUNK_HEC_INSECURESSL"                 "true"
set_var "SECRET_FOLDER_PATH"                     "$(realpath "$SECRET_FOLDER")"
set_var "ENABLE_WORKER_POLLER_SECRETS"           "true"
set_var "ENABLE_WORKER_DISCOVERY_SECRETS"        "true"
set_var "ENABLE_TRAPS_SECRETS"                   "true"
set_var "INCLUDE_UNRESOLVED_TRAP_VARBINDS"       "true"
set_var "ENABLE_FULL_WALK"                       "true"
set_var "COREFILE_ABS_PATH"                      "$(realpath "${DOCKER_COMPOSE_LOCAL}/Corefile")"
set_var "SCHEDULER_CONFIG_FILE_ABSOLUTE_PATH"    "$(realpath "$SCHEDULER_CONFIG_FILE")"
set_var "TRAPS_CONFIG_FILE_ABSOLUTE_PATH"        "$(realpath "$TRAPS_CONFIG_FILE")"
set_var "INVENTORY_FILE_ABSOLUTE_PATH"           "$(realpath "$INVENTORY_FILE")"
set_var "DISCOVERY_CONFIG_FILE_ABSOLUTE_PATH"    "$(realpath "$DISCOVERY_CONFIG_FILE")"
set_var "DISCOVERY_PATH"                         "$DISCOVERY_PATH_DIR"
set_var "SUBNET_DISCOVERY_CONCURRENCY"            "15"
set_var "UDP_CONNECTION_TIMEOUT"                  "5"
set_var "UDP_CONNECTION_RETRIES"                  "1"
set_var "COMPOSE_PROFILES"                        "discovery"

sed -i "s/###LOAD_BALANCER_ID###/$(hostname -I | cut -d " " -f1)/" "$INVENTORY_FILE"
echo $(green "Running SNMP simulators in Docker")
sudo docker run -d -p 161:161/udp tandrup/snmpsim
sudo docker run -d -p 1162:161/udp tandrup/snmpsim
sudo docker run -d -p 1163:161/udp tandrup/snmpsim
sudo docker run -d -p 1164:161/udp tandrup/snmpsim
sudo docker run -d -p 1165:161/udp tandrup/snmpsim
sudo docker run -d -p 1166:161/udp -v $(pwd)/snmpsim/data:/usr/local/snmpsim/data -e EXTRA_FLAGS="--variation-modules-dir=/usr/local/snmpsim/variation --data-dir=/usr/local/snmpsim/data" tandrup/snmpsim

"$SCRIPT_DIR/setup_autodiscovery_simulators.sh" docker || exit 1

echo $(green "Running up Docker Compose environment")
sudo docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d
wait_for_containers_to_be_up

sudo docker ps
sudo docker exec sc4snmp-inventory printenv

if [[ $1 == 'integration' ]]; then
  define_python
  deploy_poetry
fi
