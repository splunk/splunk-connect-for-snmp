#!/bin/bash
set -euo pipefail

# ===== LOAD SHARED HELPERS =====
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

# ===== DOCKER-COMPOSE PATHS =====
DOCKER_COMPOSE_ORIG="${REPO_ROOT}/docker_compose"
DOCKER_COMPOSE_LOCAL="${INT_TEST_DIR}/docker_compose"
ENV_FILE="${DOCKER_COMPOSE_LOCAL}/.env"
COMPOSE_FILE="${DOCKER_COMPOSE_LOCAL}/docker-compose.yaml"

install_docker
parse_common_args "$@"

# ===== INSTALL & CONFIGURE SNMPD (SNMPv3) =====
install_snmpd() {
  step "Installing and configuring snmpd"

  sudo apt-get update -y
  sudo apt-get install -y snmpd

  sudo sed -i -E \
    's/agentaddress[[:space:]]+127.0.0.1,\[::1\]/#agentaddress  127.0.0.1,[::1]\nagentaddress udp:1161,udp6:[::1]:1161/g' \
    /etc/snmp/snmpd.conf

  if ! sudo grep -q "r-wuser" /etc/snmp/snmpd.conf; then
    echo "" | sudo tee -a /etc/snmp/snmpd.conf >/dev/null
    echo "createUser r-wuser SHA admin1234 AES admin1234" | sudo tee -a /etc/snmp/snmpd.conf >/dev/null
    echo "rwuser r-wuser priv" | sudo tee -a /etc/snmp/snmpd.conf >/dev/null
  fi

  sudo systemctl restart snmpd
  info "snmpd configured with SNMPv3 user on udp:1161"
}

# ===== VALIDATION =====
validate_paths() {
  step "Validating paths"

  SECRET_FOLDER="${INT_TEST_DIR}/sample_v3_values"
  if [[ ! -d "$SECRET_FOLDER" ]]; then
    error "Secret folder not found: $SECRET_FOLDER"
    error "Expected structure: integration_tests/sample_v3_values/snmpv3/<secret_name>/"
    exit 1
  fi
  info "Secret folder: $SECRET_FOLDER"

  for f in \
    "${INT_TEST_DIR}/configs/scheduler-config.yaml" \
    "${INT_TEST_DIR}/configs/traps-config.yaml" \
    "${INT_TEST_DIR}/configs/inventory-tests.csv" \
    "${INT_TEST_DIR}/configs/discovery-config-docker.yaml" \
    "$ENV_FILE" \
    "${DOCKER_COMPOSE_LOCAL}/Corefile" \
    "$COMPOSE_FILE"; do
    if [[ ! -f "$f" ]]; then
      error "Required file not found: $f"
      exit 1
    fi
    info "Found: $f"
  done
}

# ===== UPDATE ENV =====
update_env() {
  local token="$1"
  step "Updating ${ENV_FILE}"

  local host_ip
  host_ip="$(hostname -I | awk '{print $1}')"

  SECRET_FOLDER="${INT_TEST_DIR}/sample_v3_values"

  set_env_var "$ENV_FILE" "SC4SNMP_IMAGE"         "snmp-local"
  set_env_var "$ENV_FILE" "SC4SNMP_TAG"           "latest"
  set_env_var "$ENV_FILE" "SC4SNMP_VERSION"       "latest"

  set_env_var "$ENV_FILE" "SPLUNK_HEC_HOST"       "$host_ip"
  set_env_var "$ENV_FILE" "SPLUNK_HEC_TOKEN"      "$token"
  set_env_var "$ENV_FILE" "SPLUNK_HEC_INSECURESSL" "true"

  set_env_var "$ENV_FILE" "SECRET_FOLDER_PATH"            "$(realpath "$SECRET_FOLDER")"
  set_env_var "$ENV_FILE" "ENABLE_TRAPS_SECRETS"          "true"
  set_env_var "$ENV_FILE" "ENABLE_WORKER_POLLER_SECRETS"  "true"
  set_env_var "$ENV_FILE" "ENABLE_WORKER_DISCOVERY_SECRETS" "true"
  set_env_var "$ENV_FILE" "INCLUDE_UNRESOLVED_TRAP_VARBINDS" "true"

  set_env_var "$ENV_FILE" "COREFILE_ABS_PATH" \
    "$(realpath "${DOCKER_COMPOSE_LOCAL}/Corefile")"

  set_env_var "$ENV_FILE" "SCHEDULER_CONFIG_FILE_ABSOLUTE_PATH" \
    "$(realpath "${INT_TEST_DIR}/configs/scheduler-config.yaml")"

  set_env_var "$ENV_FILE" "TRAPS_CONFIG_FILE_ABSOLUTE_PATH" \
    "$(realpath "${INT_TEST_DIR}/configs/traps-config.yaml")"

  set_env_var "$ENV_FILE" "INVENTORY_FILE_ABSOLUTE_PATH" \
    "$(realpath "${INT_TEST_DIR}/configs/inventory-tests.csv")"

  set_env_var "$ENV_FILE" "DISCOVERY_CONFIG_FILE_ABSOLUTE_PATH" \
    "$(realpath "${INT_TEST_DIR}/configs/discovery-config-docker.yaml")"
  set_env_var "$ENV_FILE" "DISCOVERY_PATH" "${INT_TEST_DIR}/discovery"
  set_env_var "$ENV_FILE" "COMPOSE_PROFILES" "discovery"

  set_env_var "$ENV_FILE" "IPv6_ENABLED"          "false"
  set_env_var "$ENV_FILE" "COREDNS_ADDRESS_IPv6"  ""
  set_env_var "$ENV_FILE" "ENABLE_FULL_WALK"      "true"

  sed -i "s/###LOAD_BALANCER_ID###/$(hostname -I | cut -d " " -f1)/" "${INT_TEST_DIR}/configs/inventory-tests.csv"
}
# ===== START SNMP SIMULATORS =====
start_snmp() {
  step "Starting SNMP simulators"

  echo "Starting SNMP simulators..."
  sudo docker rm -f $(sudo docker ps -aq --filter ancestor=tandrup/snmpsim) 2>/dev/null || true
  for port in 161 1162 1163 1164 1165; do
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
}

# ===== START COMPOSE =====
start_compose() {
  step "Starting SC4SNMP via Docker Compose"

  info "Building snmp-local image..."
  sudo docker build -t snmp-local .

  cd "${DOCKER_COMPOSE_LOCAL}"

  COMPOSE="sudo docker compose"

  info "Tearing down existing stack..."
  $COMPOSE \
    -f "$COMPOSE_FILE" \
    --env-file "$ENV_FILE" down --remove-orphans 2>/dev/null || true

  if sudo docker network inspect sc4snmp_network >/dev/null 2>&1; then
    sudo docker network rm sc4snmp_network
    info "Removed sc4snmp_network"
  fi

  sleep 3

  info "Starting stack..."
  $COMPOSE \
    -f "$COMPOSE_FILE" \
    --env-file "$ENV_FILE" up -d

  step "Waiting for containers to start"

  for i in {1..60}; do
    running=$(sudo docker ps --format '{{.Names}}' | grep -c worker-poller || true)

    if [[ "$running" -gt 0 ]]; then
      info "Containers up"
      break
    fi

    if [[ $i -eq 60 ]]; then
      error "Containers failed to start"
      $COMPOSE \
        -f "$COMPOSE_FILE" \
        --env-file "$ENV_FILE" logs --tail=50
      exit 1
    fi

    sleep 5
  done

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
}

# ===== RUN TESTS =====
run_tests() {
  step "Running Integration Tests"

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
  step "SC4SNMP LOCAL SETUP (Docker Compose)"
  info "REPO_ROOT:            $REPO_ROOT"
  info "INT_TEST_DIR:         $INT_TEST_DIR"
  info "DOCKER_COMPOSE_ORIG:  $DOCKER_COMPOSE_ORIG"
  info "DOCKER_COMPOSE_LOCAL: $DOCKER_COMPOSE_LOCAL"
  info "ENV_FILE:             $ENV_FILE"
  info "COMPOSE_FILE:         $COMPOSE_FILE"

  step "Copying docker_compose directory for local use"
  if [[ ! -d "$DOCKER_COMPOSE_ORIG" ]]; then
    error "Source directory not found: $DOCKER_COMPOSE_ORIG"
    exit 1
  fi
  rm -rf "$DOCKER_COMPOSE_LOCAL"
  cp -r "$DOCKER_COMPOSE_ORIG" "$DOCKER_COMPOSE_LOCAL"
  info "Copied $DOCKER_COMPOSE_ORIG -> $DOCKER_COMPOSE_LOCAL"

  install_snmpd
  start_splunk
  validate_paths
  check_splunk
  create_indexes
  [[ "$CLEAN_INDEXES" == true ]] && clean_indexes

  token=$(get_hec_token)

  update_env "$token"
  start_snmp
  "${SCRIPT_DIR}/setup_autodiscovery_simulators.sh" docker
  start_compose
  ensure_python
  deploy_poetry
  run_tests
}

main
