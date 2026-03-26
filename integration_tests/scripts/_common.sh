#!/bin/bash
#
# Shared helpers for SC4SNMP integration test scripts.
# Source this file — do not execute it directly.
#

# ===== COLORS =====
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
step()    { echo -e "\n${CYAN}====== $* ======${NC}"; }

red()     { printf "${RED}%s${NC}\n" "$*"; }
green()   { printf "${GREEN}%s${NC}\n" "$*"; }
yellow()  { printf "${YELLOW}%s${NC}\n" "$*"; }

# ===== PATHS =====
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"
INT_TEST_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${INT_TEST_DIR}/.." && pwd)"

# ===== CONFIG DEFAULTS =====
SPLUNK_HOST="localhost"
SPLUNK_PASSWORD="ch@ngeme!"
SPLUNK_PORT="8089"
SPLUNK_USER="admin"
SPLUNK_API="https://${SPLUNK_HOST}:${SPLUNK_PORT}"
CLEAN_INDEXES=false
CLEAN=false
TEST_FILTER="tests/"
SPLUNK_HOST_PROVIDED=false

REQUIRED_PYTHON_MINOR="10"
REQUIRED_PYTHON_MAX_MINOR="12"

# ===== ARG PARSING =====
parse_common_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --password)
        SPLUNK_PASSWORD="$2"
        shift 2
        ;;
      --host)
        SPLUNK_HOST="$2"
        SPLUNK_API="https://${SPLUNK_HOST}:${SPLUNK_PORT}"
        SPLUNK_HOST_PROVIDED=true
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
          traps)  TEST_FILTER="tests/test_trap_integration.py" ;;
          poller) TEST_FILTER="tests/test_poller_integration.py" ;;
          all)    TEST_FILTER="tests/" ;;
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
}

# ===== ENV FILE HELPERS =====
# Replace or append a KEY=VALUE pair in a .env file.
#   $1 — target .env file path
#   $2 — variable name
#   $3 — value
set_env_var() {
  local file="$1" key="$2" val="$3"
  grep -v "^${key}=" "$file" > "${file}.tmp" || true
  echo "${key}=${val}" >> "${file}.tmp"
  mv "${file}.tmp" "$file"
  info "  ${key}=${val}"
}

# ===== INSTALL DOCKER + DOCKER COMPOSE =====
install_docker() {
  local _old_opts
  _old_opts="$(set +o)"
  set -euo pipefail

  export DEBIAN_FRONTEND=noninteractive
  export NEEDRESTART_MODE=a

  if command -v docker >/dev/null 2>&1; then
    info "Docker already installed"
    docker --version || true
    docker compose version 2>/dev/null || true
    eval "$_old_opts"
    return 0
  fi

  step "Configuring system for non-interactive apt/dpkg/needrestart"

  APT_OPTS=(-y -q
    -o "Dpkg::Options::=--force-confdef"
    -o "Dpkg::Options::=--force-confold"
  )

  sudo -E mkdir -p /etc/needrestart/conf.d
  echo '$nrconf{restart} = "a";' | sudo -E tee /etc/needrestart/conf.d/99-noninteractive.conf >/dev/null || true

  step "Installing prerequisites"
  sudo -E apt-get update -y -q
  sudo -E apt-get install "${APT_OPTS[@]}" ca-certificates curl gnupg lsb-release

  step "Adding Docker's official GPG key"
  sudo -E install -m 0755 -d /etc/apt/keyrings
  sudo -E rm -f /etc/apt/keyrings/docker.gpg
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | sudo -E gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo -E chmod a+r /etc/apt/keyrings/docker.gpg

  step "Adding Docker APT repository"
  local codename arch
  codename="$(lsb_release -cs)"
  arch="$(dpkg --print-architecture)"
  echo "deb [arch=${arch} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${codename} stable" \
    | sudo -E tee /etc/apt/sources.list.d/docker.list >/dev/null

  step "Updating package index"
  sudo -E apt-get update -y -q

  step "Installing Docker Engine, CLI, Buildx, Compose"
  sudo -E apt-get install "${APT_OPTS[@]}" \
    docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

  step "Enabling and starting Docker service"
  sudo -E systemctl enable docker
  sudo -E systemctl start docker

  sudo -E usermod -aG docker "$USER" || true

  info "Docker installed successfully"
  docker --version || true
  docker compose version || true

  eval "$_old_opts"
}

# ===== START SPLUNK =====
start_splunk() {
  if [[ "$SPLUNK_HOST_PROVIDED" == "true" ]]; then
    info "External Splunk host specified (${SPLUNK_HOST}) — skipping local Splunk startup"
    return 0
  fi

  step "Starting Splunk in Docker"

  if sudo docker ps --format '{{.Names}}' | grep -q splunk; then
    info "Splunk container already running — skipping"
    return 0
  fi

  sudo docker pull splunk/splunk:latest

  sudo docker run -d \
    -p 8000:8000 -p 8088:8088 -p 8089:8089 \
    -e SPLUNK_GENERAL_TERMS=--accept-sgt-current-at-splunk-com \
    -e SPLUNK_START_ARGS='--accept-license' \
    -e SPLUNK_PASSWORD="${SPLUNK_PASSWORD}" \
    splunk/splunk:latest

  info "Waiting for Splunk to become healthy (timeout: 180s)..."
  local elapsed=0
  while [[ "$(sudo docker ps | grep "splunk:latest" | grep healthy)" == "" ]]; do
    if [[ $elapsed -ge 180 ]]; then
      echo ""
      error "Splunk container did not become healthy within 180s"
      sudo docker ps -a | grep splunk || true
      sudo docker logs "$(sudo docker ps -aq --filter ancestor=splunk/splunk:latest | head -1)" --tail=30 2>/dev/null || true
      exit 1
    fi
    echo -n "."
    sleep 3
    (( elapsed += 3 ))
  done
  echo ""
  info "Splunk is healthy (took ~${elapsed}s)"

  local splunk_id
  splunk_id=$(sudo docker ps | grep 'splunk/splunk:latest' | awk '{print $1}')
  sudo docker exec --user splunk "$splunk_id" bash -c \
    "echo -e '\n[diskUsage]\nminFreeSpace = 500' >> /opt/splunk/etc/system/local/server.conf"

  curl -sk -u "${SPLUNK_USER}:${SPLUNK_PASSWORD}" \
    "${SPLUNK_API}/services/server/control/restart" -X POST >/dev/null || true
  info "Waiting for Splunk to recover after restart..."
  sleep 60
  info "Splunk ready"
}

# ===== CHECK SPLUNK =====
check_splunk() {
  step "Checking Splunk connection"
  if curl -sk -u "${SPLUNK_USER}:${SPLUNK_PASSWORD}" \
      "${SPLUNK_API}/services/server/info" | grep -q "build"; then
    info "Splunk reachable at ${SPLUNK_HOST}:${SPLUNK_PORT}"
  else
    error "Cannot connect to Splunk at ${SPLUNK_API}"
    error "Check --host and --password args"
    exit 1
  fi
}

# ===== CREATE INDEXES =====
create_indexes() {
  step "Creating Splunk indexes"
  declare -A INDEXES=(
    [netmetrics]="metric"
    [em_metrics]="metric"
    [netops]="event"
    [em_logs]="event"
  )
  for name in "${!INDEXES[@]}"; do
    local dtype="${INDEXES[$name]}"
    local code
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
    -d "index=em_logs" \
    -d "indexes=em_logs,em_metrics,netmetrics,netops")

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

# ===== CLEAN INDEXES =====
clean_indexes() {
  step "Cleaning indexes"
  for idx in em_metrics em_logs netmetrics netops; do
    curl -sk -u "${SPLUNK_USER}:${SPLUNK_PASSWORD}" \
      -X DELETE "${SPLUNK_API}/services/data/indexes/$idx" >/dev/null || true
  done
  sleep 10
  create_indexes
}

# ===== PYTHON VERSION CHECK + INSTALL =====
ensure_python() {
  step "Ensuring correct Python version"

  local required_minor="$REQUIRED_PYTHON_MINOR"
  local max_minor="$REQUIRED_PYTHON_MAX_MINOR"
  local target_version="3.${required_minor}"

  _python_minor() {
    "$1" -c "import sys; print(sys.version_info.minor)" 2>/dev/null
  }

  for candidate in "python3.${required_minor}" python3 python; do
    if command -v "$candidate" &>/dev/null; then
      local minor
      minor=$(_python_minor "$candidate")
      if [[ -n "$minor" ]] && (( minor >= required_minor && minor < max_minor )); then
        PYTHON="$candidate"
        info "Using $PYTHON (3.${minor}) — satisfies >=3.${required_minor},<3.${max_minor}"
        return 0
      fi
    fi
  done

  warn "No suitable Python >=3.${required_minor},<3.${max_minor} found — installing python${target_version}"
  sudo apt-get update -y -q
  sudo apt-get install -y "python${target_version}" "python${target_version}-venv" "python${target_version}-dev"
  PYTHON="python${target_version}"

  if ! command -v "$PYTHON" &>/dev/null; then
    error "Failed to install python${target_version}"
    exit 1
  fi
  info "Installed and using $PYTHON"
}

# ===== DEPLOY POETRY =====
deploy_poetry() {
  step "Installing Poetry and Python dependencies"

  sudo apt-get update -y
  sudo apt-get install -y python3-venv python3-pip curl

  if ! command -v poetry >/dev/null 2>&1; then
    info "Installing Poetry..."
    curl -sSL https://install.python-poetry.org | "$PYTHON" -
  else
    info "Poetry already installed"
  fi

  export PATH="$HOME/.local/bin:$PATH"
  hash -r

  poetry --version || { error "Poetry installation failed"; exit 1; }

  step "Installing project dependencies"

  poetry env use "$PYTHON" || true
  poetry install

  poetry add --group dev splunk-sdk splunklib pysnmplib || true
}
