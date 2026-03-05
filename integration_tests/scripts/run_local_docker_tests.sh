

#!/bin/bash
set -euo pipefail

# ===== COLORS =====
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
step()    { echo -e "\n${CYAN}====== $* ======${NC}"; }

# ===== PATHS =====
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INT_TEST_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${INT_TEST_DIR}/.." && pwd)"
ENV_FILE="${REPO_ROOT}/docker_compose/.env"
COMPOSE_FILE="${REPO_ROOT}/docker_compose/docker-compose.yaml"

# ===== CONFIG DEFAULTS =====
SPLUNK_HOST="localhost"
SPLUNK_PASSWORD="ch@ngeme!"
SPLUNK_PORT="8089"
SPLUNK_USER="admin"
SPLUNK_API="https://${SPLUNK_HOST}:${SPLUNK_PORT}"
CLEAN_INDEXES=false
TEST_FILTER="tests/"


# ===== INSTALL DOCKER + DOCKER COMPOSE =====
install_docker() {

if ! command -v docker >/dev/null 2>&1; then
    step "Installing Docker"

    sudo apt-get update
    sudo apt-get install -y docker.io curl

    sudo systemctl start docker
    sudo systemctl enable docker

    info "Docker installed "
fi

if ! command -v docker-compose >/dev/null 2>&1; then
    step "Installing docker-compose"

    sudo curl -L \
      "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
      -o /usr/local/bin/docker-compose

    sudo chmod +x /usr/local/bin/docker-compose

    info "docker-compose installed "
fi
}

install_docker


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


# ===== VALIDATION =====
validate_paths() {
  step "Validating paths"

  # FIX 1: Correct secret folder path (was wrong in original — data/sample_v3_values doesn't exist)
  SECRET_FOLDER="${INT_TEST_DIR}/sample_v3_values"
  if [[ ! -d "$SECRET_FOLDER" ]]; then
    error "Secret folder not found: $SECRET_FOLDER"
    error "Expected structure: integration_tests/sample_v3_values/snmpv3/<secret_name>/"
    exit 1
  fi
  info "Secret folder: $SECRET_FOLDER "

  # Validate configs
  for f in \
    "${INT_TEST_DIR}/configs/scheduler-config.yaml" \
    "${INT_TEST_DIR}/configs/traps-config.yaml" \
    "${INT_TEST_DIR}/configs/inventory-tests.csv" \
    "${REPO_ROOT}/docker_compose/Corefile" \
    "$ENV_FILE" \
    "$COMPOSE_FILE"; do
    if [[ ! -f "$f" ]]; then
      error "Required file not found: $f"
      exit 1
    fi
    info "Found: $f "
  done
}

# ===== CHECK SPLUNK =====
check_splunk() {
  step "Checking Splunk connection"
  if curl -sk -u "${SPLUNK_USER}:${SPLUNK_PASSWORD}" \
      "${SPLUNK_API}/services/server/info" | grep -q "build"; then
    info "Splunk reachable at ${SPLUNK_HOST}:${SPLUNK_PORT} "
  else
    error "Cannot connect to Splunk at ${SPLUNK_API}"
    error "Check --host and --password args"
    exit 1
  fi
}

# ===== CREATE INDEXES =====
create_indexes() {
  step "Creating Splunk indexes"
  # FIX 2: Use exact index names the tests search against
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

# ===== GET HEC TOKEN =====
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

  # ONLY print token to stdout - nothing else
  echo "$token"
}


# ===== CLEAN INDEXES =====
clean_indexes() {
  step "Cleaning indexes"

  for idx in em_metrics em_events em_meta netmetrics netops; do
    curl -sk -u "${SPLUNK_USER}:${SPLUNK_PASSWORD}" \
      -X DELETE "${SPLUNK_API}/services/data/indexes/$idx" >/dev/null || true
  done

  sleep 10
  create_indexes
}
# ===== UPDATE ENV =====
update_env() {
  local token="$1"
  step "Updating ${ENV_FILE}"

  # FIX 3: Correct helper — removes then appends (truly idempotent)
  set_var() {
    local key="$1" val="$2"
    grep -v "^${key}=" "$ENV_FILE" > "${ENV_FILE}.tmp" || true
    echo "${key}=${val}" >> "${ENV_FILE}.tmp"
    mv "${ENV_FILE}.tmp" "$ENV_FILE"
    info "  ${key}=${val}"
  }

  local host_ip
  host_ip="$(hostname -I | awk '{print $1}')"

  # FIX 4: Correct SECRET_FOLDER_PATH — was pointing to non-existent data/ subfolder
  SECRET_FOLDER="${INT_TEST_DIR}/sample_v3_values"

  # FIX 5: Correct inventory/config paths — they live in configs/ subdir
  set_var "SPLUNK_HEC_HOST"       "$host_ip"
  set_var "SPLUNK_HEC_TOKEN"      "$token"
  set_var "SPLUNK_HEC_INSECURESSL" "true"

  set_var "SECRET_FOLDER_PATH"            "$(realpath "$SECRET_FOLDER")"
  set_var "ENABLE_TRAPS_SECRETS"          "true"
  set_var "ENABLE_WORKER_POLLER_SECRETS"  "true"

  set_var "COREFILE_ABS_PATH" \
    "$(realpath "${REPO_ROOT}/docker_compose/Corefile")"

  set_var "SCHEDULER_CONFIG_FILE_ABSOLUTE_PATH" \
    "$(realpath "${INT_TEST_DIR}/configs/scheduler-config.yaml")"

  set_var "TRAPS_CONFIG_FILE_ABSOLUTE_PATH" \
    "$(realpath "${INT_TEST_DIR}/configs/traps-config.yaml")"

  set_var "INVENTORY_FILE_ABSOLUTE_PATH" \
    "$(realpath "${INT_TEST_DIR}/configs/inventory-tests.csv")"

  set_var "IPv6_ENABLED"          "false"
  set_var "COREDNS_ADDRESS_IPv6"  ""

  # FIX 6: Reduce walk interval for local testing (pipeline uses 600, too slow locally)
  DOCKER_BRIDGE_IP=$(ip addr show docker0 2>/dev/null | grep "inet " | awk '{print $2}' | cut -d/ -f1 || echo "172.17.0.1")
  info "Docker bridge IP: $DOCKER_BRIDGE_IP"

  # FIX 7: Patch inventory with correct IP and reduced walk interval (60s not 600s)
  echo "address,port,version,community,secret,security_engine,walk_interval,profiles,smart_profiles,delete" \
    > "${INT_TEST_DIR}/configs/inventory-tests.csv"
  echo "${DOCKER_BRIDGE_IP},,2c,public,,,60,generic_switch,," \
    >> "${INT_TEST_DIR}/configs/inventory-tests.csv"
  info "Inventory set to: ${DOCKER_BRIDGE_IP} with walk_interval=60"
}

# ===== START SNMP SIMULATORS =====
start_snmp() {
  step "Starting SNMP simulators"

    echo "Starting SNMP simulators..."
  sudo docker rm -f $(sudo docker ps -aq --filter ancestor=tandrup/snmpsim) 2>/dev/null || true
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
}
start_compose() {

  step "Starting SC4SNMP via Docker Compose"

  cd "${REPO_ROOT}"

  COMPOSE="sudo docker-compose"

  # Stop old containers
  info "Tearing down existing stack..."
  $COMPOSE -f "$COMPOSE_FILE" down --remove-orphans 2>/dev/null || true

  # Remove old network
  if sudo docker network inspect sc4snmp_network >/dev/null 2>&1; then
      sudo docker network rm sc4snmp_network
      info "Removed sc4snmp_network"
  fi

  sleep 3

  # Build image
  info "Building snmp-local image..."
  sudo docker build -t snmp-local .

  # Start containers
  info "Starting stack..."
  $COMPOSE -f "$COMPOSE_FILE" up -d

  # Wait for worker container
  step "Waiting for containers to start"

  for i in {1..60}; do

    running=$(sudo docker ps --format '{{.Names}}' | grep -c worker-poller || true)

    if [[ "$running" -gt 0 ]]; then
      info "Containers up "
      break
    fi

    if [[ $i -eq 60 ]]; then
      error "Containers failed to start"
      $COMPOSE -f "$COMPOSE_FILE" logs --tail=50
      exit 1
    fi

    sleep 5

  done


  # Wait for first poll cycle
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

# ===== RUN TESTS =====
run_tests() {
  step "Running Integration Tests"

  # FIX 13: trap_ip must be the docker bridge IP, not the host's primary IP
  local trap_ip
  trap_ip=$(ip addr show docker0 2>/dev/null | grep "inet " | awk '{print $2}' | cut -d/ -f1 || echo "172.17.0.1")
  info "Using trap_external_ip: $trap_ip"
  info "Running filter: ${TEST_FILTER}"

  cd "${INT_TEST_DIR}"
  poetry run pytest \
    --splunk_host="${SPLUNK_HOST}" \
    --splunk_port="${SPLUNK_PORT}" \
    --splunk_user="${SPLUNK_USER}" \
    --splunk_password="${SPLUNK_PASSWORD}" \
    --trap_external_ip="${trap_ip}" \
    --sc4snmp_deployment="docker-compose" \
    -v \
    ${TEST_FILTER}
}

# ===== MAIN =====
main() {
  step "SC4SNMP LOCAL SETUP"
  info "REPO_ROOT:    $REPO_ROOT"
  info "INT_TEST_DIR: $INT_TEST_DIR"
  info "ENV_FILE:     $ENV_FILE"
  info "COMPOSE_FILE: $COMPOSE_FILE"

  validate_paths
  check_splunk
  create_indexes
  [[ "$CLEAN_INDEXES" == true ]] && clean_indexes

  token=$(get_hec_token)

  update_env "$token"
  start_snmp
  start_compose
  define_python
  deploy_poetry
  run_tests
}

main




