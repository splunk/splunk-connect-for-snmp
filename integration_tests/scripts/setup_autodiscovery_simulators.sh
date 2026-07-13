#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INT_TEST_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DATA_ROOT="${INT_TEST_DIR}/autodiscovery/snmpsim-data"
DISCOVERY_OUTPUT_DIR="${DISCOVERY_OUTPUT_DIR:-${INT_TEST_DIR}/discovery}"
SIMULATOR_IMAGE="${AUTODISCOVERY_SIMULATOR_IMAGE:-tandrup/snmpsim}"
DEPLOYMENT_MODE="${1:-microk8s}"
case "${DEPLOYMENT_MODE}" in
  docker)
    DEFAULT_SIMULATOR_NAMESPACE="docker-agent-simulator"
    V1_PREFIX="10.4.4"
    V2_PREFIX="10.5.5"
    V3_PREFIX="10.6.6"
    ;;
  microk8s)
    DEFAULT_SIMULATOR_NAMESPACE="microk8s-agent-simulator"
    V1_PREFIX="10.1.1"
    V2_PREFIX="10.2.2"
    V3_PREFIX="10.3.3"
    ;;
  *)
    printf 'Usage: %s [docker|microk8s]\n' "$0" >&2
    exit 2
    ;;
esac
SIMULATOR_NAMESPACE="${AUTODISCOVERY_SIMULATOR_NAMESPACE:-${DEFAULT_SIMULATOR_NAMESPACE}}"
V1_CIDR="${V1_PREFIX}.0/24"
V2_CIDR="${V2_PREFIX}.0/24"
V3_CIDR="${V3_PREFIX}.0/24"
V3_SHA_ENGINE="8000000903000A3900000101"
V3_MD5_ENGINE="8000000903000A3900000102"
V3_SHA_USER="autodiscovery-sha"
V3_MD5_USER="autodiscovery-md5"
V3_SHA_AUTH_KEY="AuthPass1"
V3_SHA_PRIV_KEY="PrivPass1"
V3_MD5_AUTH_KEY="AuthPass2"
V3_MD5_PRIV_KEY="PrivPass2"

V2C_IPS=("${V1_PREFIX}."{1..9})
V3_SHA_IPS=("${V2_PREFIX}."{1..9})
V3_MD5_IPS=("${V3_PREFIX}."{1..9})
SIMULATOR_IPS=("${V2C_IPS[@]}" "${V3_SHA_IPS[@]}" "${V3_MD5_IPS[@]}")
AGENT_COUNT="${#SIMULATOR_IPS[@]}"
VARIATIONS=(v2c v3-sha v3-md5)
declare -A VAR_PREFIX=([v2c]=v1 [v3-sha]=v2 [v3-md5]=v3)
declare -A VAR_IP_PREFIX=([v2c]="${V1_PREFIX}" [v3-sha]="${V2_PREFIX}" [v3-md5]="${V3_PREFIX}")
declare -A VAR_DATA_FILE=([v2c]=public.snmprec [v3-sha]=1.3.6.1.6.1.1.0.snmprec [v3-md5]=1.3.6.1.6.1.1.0.snmprec)
declare -A VAR_FLAGS=(
  [v2c]="--v2c-arch --data-dir=/usr/local/snmpsim/data"
  [v3-sha]="--v3-only --v3-engine-id=${V3_SHA_ENGINE} --v3-context-engine-id=${V3_SHA_ENGINE} --v3-user=${V3_SHA_USER} --v3-auth-key=${V3_SHA_AUTH_KEY} --v3-auth-proto=SHA --v3-priv-key=${V3_SHA_PRIV_KEY} --v3-priv-proto=AES --data-dir=/usr/local/snmpsim/data"
  [v3-md5]="--v3-only --v3-engine-id=${V3_MD5_ENGINE} --v3-context-engine-id=${V3_MD5_ENGINE} --v3-user=${V3_MD5_USER} --v3-auth-key=${V3_MD5_AUTH_KEY} --v3-auth-proto=MD5 --v3-priv-key=${V3_MD5_PRIV_KEY} --v3-priv-proto=AES --data-dir=/usr/local/snmpsim/data"
)
CURRENT_STAGE="initialization"

# Color
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

function red {
  printf '%b%s%b\n' "${RED}" "$*" "${NC}"
}

function green {
  printf '%b%s%b\n' "${GREEN}" "$*" "${NC}"
}

function yellow {
  printf '%b%s%b\n' "${YELLOW}" "$*" "${NC}"
}

kctl() {
  sudo microk8s kubectl "$@"
}

dump_microk8s_diagnostics() {
  echo $(green "[INFO] MicroK8s status:")
  timeout 20s sudo microk8s status || true
  echo $(green "[INFO] MicroK8s node and namespace resources:")
  timeout 20s sudo microk8s kubectl get nodes -o wide || true
  timeout 20s sudo microk8s kubectl get all -n "${SIMULATOR_NAMESPACE}" -o wide || true
  echo $(green "[INFO] Recent ${SIMULATOR_NAMESPACE} events:")
  timeout 20s sudo microk8s kubectl get events \
    -n "${SIMULATOR_NAMESPACE}" --sort-by=.lastTimestamp || true
  echo $(green "[INFO] Recent simulator container logs:")
  timeout 30s sudo microk8s kubectl logs \
    -n "${SIMULATOR_NAMESPACE}" \
    -l sc4snmp.integration.autodiscovery=true \
    --all-containers=true --prefix=true --tail=50 --ignore-errors=true || true
  echo $(green "[INFO] Kubelite service status:")
  sudo systemctl status snap.microk8s.daemon-kubelite \
    --no-pager --full || true
  echo $(green "[INFO] Recent kubelite journal:")
  sudo journalctl -u snap.microk8s.daemon-kubelite \
    --no-pager -n 150 || true
}

handle_error() {
  local exit_code="$1"
  local line_number="$2"

  trap - ERR
  echo $(red "[ERROR] Autodiscovery setup failed in '${CURRENT_STAGE}' at line ${line_number} (exit ${exit_code}).")
  dump_microk8s_diagnostics
  exit "${exit_code}"
}

trap 'handle_error "$?" "$LINENO"' ERR

wait_for_microk8s_api() {
  local timeout_seconds="${1:-180}"
  local required_successes="${2:-5}"
  local deadline=$((SECONDS + timeout_seconds))
  local consecutive_successes=0
  local attempt=0

  while (( SECONDS < deadline )); do
    attempt=$((attempt + 1))
    if timeout 15s sudo microk8s kubectl get --raw=/readyz >/dev/null 2>&1; then
      consecutive_successes=$((consecutive_successes + 1))
      if (( consecutive_successes >= required_successes )); then
        echo $(green "[DONE] MicroK8s API remained ready for ${required_successes} consecutive checks")
        return 0
      fi
    else
      consecutive_successes=0
      echo $(yellow "[INFO] MicroK8s API is not ready (attempt ${attempt}); retrying")
    fi
    sleep 3
  done

  echo $(red "[ERROR] MicroK8s API did not become stable within ${timeout_seconds} seconds")
  return 1
}

apply_k8s_manifest() {
  local description="$1"
  local manifest
  local output=""
  local attempt

  manifest="$(cat)"
  for attempt in 1 2 3 4; do
    if output="$(printf '%s\n' "${manifest}" | \
        sudo microk8s kubectl apply -f - 2>&1)"; then
      if [[ -n "${output}" ]]; then
        while IFS= read -r output_line; do
          echo $(green "[INFO] ${output_line}")
        done <<< "${output}"
      fi
      return 0
    fi

    echo $(yellow "[INFO] ${description} apply attempt ${attempt}/4 failed: ${output}")
    if (( attempt < 4 )); then
      wait_for_microk8s_api 45 2 || true
    fi
  done

  echo $(red "[ERROR] Unable to apply ${description} after four attempts")
  return 1
}

require_file() {
  [[ -f "$1" ]] || {
    echo $(red "Required autodiscovery fixture is missing: $1") >&2
    exit 1
  }
}

format_ips() {
  local address
  local joined=""

  for address in "$@"; do
    if [[ -n "${joined}" ]]; then
      joined="${joined}, "
    fi
    joined="${joined}${address}"
  done
  printf "%s" "${joined}"
}

agent_name() {
  printf 'snmp-agent-%s-%03d' "${VAR_PREFIX[$1]}" "$2"
}

agent_ip() {
  printf '%s.%d' "${VAR_IP_PREFIX[$1]}" "$2"
}

for_each_agent() {
  local callback="$1"
  local variation ordinal

  for variation in "${VARIATIONS[@]}"; do
    for ordinal in {1..9}; do
      "${callback}" "${variation}" \
        "$(agent_name "${variation}" "${ordinal}")" \
        "$(agent_ip "${variation}" "${ordinal}")"
    done
  done
}

for variation in "${VARIATIONS[@]}"; do
  require_file "${DATA_ROOT}/${variation}/${VAR_DATA_FILE[$variation]}"
done

CURRENT_STAGE="Installing the SNMP test client"
echo $(green "[STEP] ${CURRENT_STAGE}")
sudo apt-get update -y -q
sudo apt-get install -y -q snmp
echo $(green "[DONE] SNMP test client installed")

CURRENT_STAGE="Preparing SC4SNMP discovery output"
echo $(green "[STEP] ${CURRENT_STAGE}")
echo $(green "[INFO] Removing stale discovery CSV and lock files")
sudo rm -f "${DISCOVERY_OUTPUT_DIR}/discovery_devices.csv" \
  "${DISCOVERY_OUTPUT_DIR}/discovery_devices.lock"
sudo install -d -o 10001 -g 10001 -m 0755 "${DISCOVERY_OUTPUT_DIR}"
chmod -R a+rX "${DATA_ROOT}"
echo $(green "[DONE] Discovery directory ready: ${DISCOVERY_OUTPUT_DIR} (owner 10001:10001, mode 0755)")

create_simulator_configmap() {
  local name="$1"
  local key="$2"
  local source_file="$3"
  local manifest

  manifest="$(kctl create configmap "${name}" \
    -n "${SIMULATOR_NAMESPACE}" \
    --from-file="${key}=${source_file}" \
    --dry-run=client -o yaml)"
  apply_k8s_manifest "ConfigMap ${SIMULATOR_NAMESPACE}/${name}" <<< "${manifest}"
}

ip_to_int() {
  local ip="$1"
  local a b c d

  IFS=. read -r a b c d <<< "${ip}"
  echo $(( (a << 24) + (b << 16) + (c << 8) + d ))
}

cidr_contains_ip() {
  local cidr="$1"
  local ip="$2"
  local network="${cidr%/*}"
  local prefix="${cidr#*/}"
  local network_int
  local ip_int
  local mask

  network_int="$(ip_to_int "${network}")"
  ip_int="$(ip_to_int "${ip}")"
  mask=$(( (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF ))
  (( (network_int & mask) == (ip_int & mask) ))
}

calico_pool_contains_range() {
  local first_ip="$1"
  local last_ip="$2"
  local pool_cidr

  while read -r pool_cidr; do
    [[ -n "${pool_cidr}" ]] || continue
    if cidr_contains_ip "${pool_cidr}" "${first_ip}" && \
      cidr_contains_ip "${pool_cidr}" "${last_ip}"; then
      return 0
    fi
  done < <(kctl get ippools.crd.projectcalico.org \
    -o jsonpath='{range .items[*]}{.spec.cidr}{"\n"}{end}')

  return 1
}

ensure_calico_pool_for_range() {
  local pool_name="$1"
  local cidr="$2"
  local first_ip="$3"
  local last_ip="$4"

  if calico_pool_contains_range "${first_ip}" "${last_ip}"; then
    echo $(green "[INFO] ${cidr} is already covered by a Calico IPPool")
    return 0
  fi

  echo $(green "[INFO] Creating Calico IPPool ${pool_name} for ${cidr}")
  apply_k8s_manifest "Calico IPPool ${pool_name}" <<YAML
apiVersion: crd.projectcalico.org/v1
kind: IPPool
metadata:
  name: ${pool_name}
spec:
  cidr: ${cidr}
  blockSize: 26
  ipipMode: Never
  vxlanMode: Always
  natOutgoing: true
  nodeSelector: all()
  allowedUses:
    - Workload
YAML
}

assert_simulator_ips_available() {
  local namespace
  local pod_name
  local used_ip
  local requested_ip
  local pod_inventory

  pod_inventory="$(kctl get pods -A \
    -o custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name,IP:.status.podIP \
    --no-headers)"
  while read -r namespace pod_name used_ip; do
    [[ -n "${used_ip}" && "${used_ip}" != "<none>" ]] || continue
    for requested_ip in "${SIMULATOR_IPS[@]}"; do
      if [[ "${used_ip}" == "${requested_ip}" ]]; then
        echo $(red "Requested simulator IP ${requested_ip} is already used by Pod ${namespace}/${pod_name}") >&2
        return 1
      fi
    done
  done <<< "${pod_inventory}"
  echo $(green "[DONE] All ${AGENT_COUNT} requested simulator IPs are currently available")
}

deploy_k8s_agent() {
  local variation="$1" name="$2" ip="$3"

  echo $(green "[INFO] Applying static Pod ${SIMULATOR_NAMESPACE}/${name} at ${ip} (${variation})")
  apply_k8s_manifest "simulator Pod ${SIMULATOR_NAMESPACE}/${name}" <<YAML
apiVersion: v1
kind: Pod
metadata:
  name: ${name}
  namespace: ${SIMULATOR_NAMESPACE}
  labels:
    agent-id: ${name}
    variation: ${variation}
    sc4snmp.integration.autodiscovery: "true"
  annotations:
    cni.projectcalico.org/ipAddrs: '["${ip}"]'
spec:
  restartPolicy: Always
  containers:
    - name: snmpsim
      image: ${SIMULATOR_IMAGE}
      imagePullPolicy: IfNotPresent
      command: ["/bin/sh", "-c"]
      args:
        - >-
          exec snmpsimd.py ${VAR_FLAGS[$variation]}
          --agent-udpv4-endpoint=0.0.0.0:161
          --process-user=snmpsim
          --process-group=nogroup
      ports:
        - name: snmp
          containerPort: 161
          protocol: UDP
      volumeMounts:
        - name: simulator-data
          mountPath: /usr/local/snmpsim/data
          readOnly: true
  volumes:
    - name: simulator-data
      configMap:
        name: autodiscovery-${variation}-data
YAML
}

verify_k8s_static_agent() {
  local name="$2" expected_ip="$3" actual_ip
  actual_ip="$(kctl get pod "${name}" -n "${SIMULATOR_NAMESPACE}" \
    -o jsonpath='{.status.podIP}')"
  [[ "${actual_ip}" == "${expected_ip}" ]] || {
    echo $(red "Pod ${name} expected ${expected_ip}, received ${actual_ip}") >&2
    return 1
  }
}

start_microk8s_agents() {
  if ! command -v microk8s >/dev/null 2>&1; then
    CURRENT_STAGE="Installing MicroK8s for autodiscovery simulators"
    echo $(green "[STEP] ${CURRENT_STAGE}")
    sudo snap install microk8s --classic
    echo $(green "[DONE] MicroK8s installed for the agent simulator namespace")
  fi

  CURRENT_STAGE="Starting MicroK8s for autodiscovery simulators"
  echo $(green "[STEP] ${CURRENT_STAGE}")
  sudo microk8s start
  echo $(green "[DONE] MicroK8s services started for the agent simulator namespace")

  CURRENT_STAGE="Waiting for the MicroK8s API"
  echo $(green "[STEP] ${CURRENT_STAGE}")
  wait_for_microk8s_api 180 5

  CURRENT_STAGE="Preparing the MicroK8s simulator namespace"
  echo $(green "[STEP] ${CURRENT_STAGE}")
  kctl delete namespace "${SIMULATOR_NAMESPACE}" --ignore-not-found=true
  kctl create namespace "${SIMULATOR_NAMESPACE}"
  assert_simulator_ips_available
  echo $(green "[DONE] Namespace ${SIMULATOR_NAMESPACE} is ready")

  CURRENT_STAGE="Preparing static Calico simulator ranges"
  echo $(green "[STEP] ${CURRENT_STAGE}")
  kctl get crd ippools.crd.projectcalico.org >/dev/null
  ensure_calico_pool_for_range \
    "sc4snmp-${DEPLOYMENT_MODE}-autodiscovery-v1-pool" \
    "${V1_CIDR}" "${V1_PREFIX}.1" "${V1_PREFIX}.9"
  ensure_calico_pool_for_range \
    "sc4snmp-${DEPLOYMENT_MODE}-autodiscovery-v2-pool" \
    "${V2_CIDR}" "${V2_PREFIX}.1" "${V2_PREFIX}.9"
  ensure_calico_pool_for_range \
    "sc4snmp-${DEPLOYMENT_MODE}-autodiscovery-v3-pool" \
    "${V3_CIDR}" "${V3_PREFIX}.1" "${V3_PREFIX}.9"
  echo $(green "[DONE] Static simulator ranges are available through Calico")

  CURRENT_STAGE="Loading compact SNMP simulator data"
  echo $(green "[STEP] ${CURRENT_STAGE}")
  echo $(green "[INFO] Creating v2c, v3 SHA/AES, and v3 MD5/AES ConfigMaps")
  for variation in "${VARIATIONS[@]}"; do
    create_simulator_configmap "autodiscovery-${variation}-data" \
      "${VAR_DATA_FILE[$variation]}" \
      "${DATA_ROOT}/${variation}/${VAR_DATA_FILE[$variation]}"
  done
  echo $(green "[DONE] Loaded three simulator data ConfigMaps into ${SIMULATOR_NAMESPACE}")

  CURRENT_STAGE="Deploying MicroK8s SNMP simulators"
  echo $(green "[STEP] ${CURRENT_STAGE}")
  echo $(green "[INFO] Creating ${AGENT_COUNT} static Pods in ${SIMULATOR_NAMESPACE}")
  for_each_agent deploy_k8s_agent

  kctl wait --for=condition=Ready pod \
    -n "${SIMULATOR_NAMESPACE}" \
    -l sc4snmp.integration.autodiscovery=true \
    --timeout=300s
  echo $(green "[DONE] All ${AGENT_COUNT} simulator Pods are ready")

  echo $(green "[INFO] Running: microk8s kubectl get pods -n ${SIMULATOR_NAMESPACE} -o wide")
  kctl get pods \
    -n "${SIMULATOR_NAMESPACE}" \
    -l sc4snmp.integration.autodiscovery=true \
    -o wide
  for_each_agent verify_k8s_static_agent
  echo $(green "[DONE] Kubernetes reports all ${AGENT_COUNT} requested simulator Pod IPs exactly")
}

start_microk8s_agents

verify_v2c_agent() {
  local address="$1"
  local attempt

  for attempt in $(seq 1 20); do
    if snmpget -v2c -c public -On "${address}:161" \
        1.3.6.1.2.1.1.1.0 >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo $(red "Simulator ${address}:161 did not return a v2c response") >&2
  return 1
}

for address in "${V2C_IPS[@]}"; do
  verify_v2c_agent "${address}"
done

CURRENT_STAGE="Reporting autodiscovery simulator readiness"
echo $(green "[STEP] ${CURRENT_STAGE}")
echo $(green "[DONE] integration_v2c: 9/9 agents ready -> $(format_ips "${V2C_IPS[@]}")")
echo $(green "[DONE] integration_v3_sha: 9/9 agents ready -> $(format_ips "${V3_SHA_IPS[@]}")")
echo $(green "[DONE] integration_v3_md5: 9/9 agents ready -> $(format_ips "${V3_MD5_IPS[@]}")")
echo $(green "[DONE] Autodiscovery environment ready: ${AGENT_COUNT}/${AGENT_COUNT} MicroK8s agents available for ${DEPLOYMENT_MODE} SC4SNMP")
