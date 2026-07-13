#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INT_TEST_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DATA_ROOT="${INT_TEST_DIR}/autodiscovery/snmpsim-data"
DISCOVERY_OUTPUT_DIR="${DISCOVERY_OUTPUT_DIR:-${INT_TEST_DIR}/discovery}"
SIMULATOR_IMAGE="${AUTODISCOVERY_SIMULATOR_IMAGE:-tandrup/snmpsim}"
BACKEND_MODE="${1:-docker}"
SIMULATOR_NAMESPACE="${AUTODISCOVERY_SIMULATOR_NAMESPACE:-agent-simulator}"
DOCKER_NETWORK_V1="${AUTODISCOVERY_DOCKER_NETWORK_V1:-sc4snmp-autodiscovery-v1}"
DOCKER_NETWORK_V2="${AUTODISCOVERY_DOCKER_NETWORK_V2:-sc4snmp-autodiscovery-v2}"
V1_CIDR="10.1.1.0/24"
V2_CIDR="10.2.2.0/24"
V1_DOCKER_GATEWAY="10.1.1.254"
V2_DOCKER_GATEWAY="10.2.2.254"
LEGACY_DUMMY_INTERFACE="${AUTODISCOVERY_DUMMY_INTERFACE:-sc4snmp-auto}"
NGINX_CONFIG="/etc/nginx/sc4snmp-autodiscovery-nginx.conf"
NGINX_STREAM_CONFIG="/etc/nginx/sc4snmp-autodiscovery-stream.conf"
NGINX_SERVICE="sc4snmp-autodiscovery-nginx.service"
NGINX_V2C_PORT=2161
NGINX_V3_SHA_PORT=2162
NGINX_V3_MD5_PORT=2163

V3_SHA_ENGINE="8000000903000A3900000101"
V3_MD5_ENGINE="8000000903000A3900000102"
V3_SHA_USER="autodiscovery-sha"
V3_MD5_USER="autodiscovery-md5"
V3_SHA_AUTH_KEY="AuthPass1"
V3_SHA_PRIV_KEY="PrivPass1"
V3_MD5_AUTH_KEY="AuthPass2"
V3_MD5_PRIV_KEY="PrivPass2"

V2C_IPS=(
  10.1.1.1 10.1.1.2 10.1.1.3 10.1.1.4 10.1.1.5
  10.1.1.6 10.1.1.7 10.1.1.8 10.1.1.9
)
V3_SHA_IPS=(10.2.2.1 10.2.2.2 10.2.2.3 10.2.2.4 10.2.2.5)
V3_MD5_IPS=(10.2.2.6 10.2.2.7 10.2.2.8 10.2.2.9)
SIMULATOR_IPS=("${V2C_IPS[@]}" "${V3_SHA_IPS[@]}" "${V3_MD5_IPS[@]}")
CURRENT_STAGE="initialization"

# Color
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

function red {
    printf "${RED}$@${NC}\n"
}

function green {
    printf "${GREEN}$@${NC}\n"
}

function yellow {
    printf "${YELLOW}$@${NC}\n"
}

if [[ "${BACKEND_MODE}" != "docker" && "${BACKEND_MODE}" != "microk8s" ]]; then
  echo $(red "Usage: $0 [docker|microk8s]") >&2
  exit 2
fi

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
  echo $(green "[INFO] Autodiscovery Nginx service status:")
  sudo systemctl status "${NGINX_SERVICE}" --no-pager --full || true
}

handle_error() {
  local exit_code="$1"
  local line_number="$2"

  trap - ERR
  echo $(red "[ERROR] Autodiscovery setup failed in '${CURRENT_STAGE}' at line ${line_number} (exit ${exit_code}).")
  if [[ "${BACKEND_MODE}" == "microk8s" ]]; then
    dump_microk8s_diagnostics
  fi
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

require_file "${DATA_ROOT}/v2c/public.snmprec"
require_file "${DATA_ROOT}/v3-sha/1.3.6.1.6.1.1.0.snmprec"
require_file "${DATA_ROOT}/v3-md5/1.3.6.1.6.1.1.0.snmprec"

CURRENT_STAGE="Installing autodiscovery host dependencies"
echo $(green "[STEP] ${CURRENT_STAGE}")
echo $(green "[INFO] Installing Nginx, the Nginx stream module, and the SNMP test client")
sudo apt-get update -y -q
sudo apt-get install -y -q nginx libnginx-mod-stream snmp
echo $(green "[DONE] Nginx UDP stream support and SNMP client installed")

CURRENT_STAGE="Preparing SC4SNMP discovery output"
echo $(green "[STEP] ${CURRENT_STAGE}")
echo $(green "[INFO] Removing stale discovery CSV and lock files")
sudo rm -f "${DISCOVERY_OUTPUT_DIR}/discovery_devices.csv" \
  "${DISCOVERY_OUTPUT_DIR}/discovery_devices.lock"
sudo install -d -o 10001 -g 10001 -m 0755 "${DISCOVERY_OUTPUT_DIR}"
chmod -R a+rX "${DATA_ROOT}"
echo $(green "[DONE] Discovery directory ready: ${DISCOVERY_OUTPUT_DIR} (owner 10001:10001, mode 0755)")

CURRENT_STAGE="Removing legacy proxy addresses"
echo $(green "[STEP] ${CURRENT_STAGE}")
echo $(green "[INFO] Stopping the previous Nginx fixture before replacing its routes")
sudo systemctl stop "${NGINX_SERVICE}" >/dev/null 2>&1 || true
if ip link show "${LEGACY_DUMMY_INTERFACE}" >/dev/null 2>&1; then
  sudo ip link delete "${LEGACY_DUMMY_INTERFACE}"
fi
echo $(green "[DONE] Removed legacy 10.250.0.x proxy addresses")

start_docker_agent() {
  local name="$1"
  local backend_ip="$2"
  local variation="$3"
  local range_variation="$4"
  local network="$5"
  local data_dir="$6"
  local extra_flags="$7"

  sudo docker run -d \
    --name "$name" \
    --label sc4snmp.integration.autodiscovery=true \
    --label "sc4snmp.integration.variation=${variation}" \
    --label "sc4snmp.integration.range-variation=${range_variation}" \
    --network "${network}" \
    --ip "$backend_ip" \
    --mount "type=bind,src=${data_dir},dst=/usr/local/snmpsim/data,readonly" \
    "${SIMULATOR_IMAGE}" \
    /bin/sh -c "exec snmpsimd.py ${extra_flags} --agent-udpv4-endpoint=0.0.0.0:161 --process-user=snmpsim --process-group=nogroup" \
    >/dev/null

}

verify_docker_agent_ip() {
  local name="$1"
  local network="$2"
  local expected_ip="$3"
  local actual_ip

  actual_ip="$(sudo docker inspect --format \
    "{{with index .NetworkSettings.Networks \"${network}\"}}{{.IPAddress}}{{end}}" \
    "${name}")"
  if [[ "${actual_ip}" != "${expected_ip}" ]]; then
    echo $(red "Container ${name} expected ${expected_ip}, received ${actual_ip}") >&2
    return 1
  fi
}

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
  kctl label configmap "${name}" \
    -n "${SIMULATOR_NAMESPACE}" \
    sc4snmp.integration.autodiscovery=true --overwrite
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
  echo $(green "[DONE] All 18 requested simulator IPs are currently available")
}

deploy_k8s_agent() {
  local name="$1"
  local ip="$2"
  local variation="$3"
  local range_variation="$4"
  local configmap="$5"
  local extra_flags="$6"

  echo $(green "[INFO] Applying static Pod ${SIMULATOR_NAMESPACE}/${name} at ${ip} (${variation})")
  apply_k8s_manifest "simulator Pod ${SIMULATOR_NAMESPACE}/${name}" <<YAML
apiVersion: v1
kind: Pod
metadata:
  name: ${name}
  namespace: ${SIMULATOR_NAMESPACE}
  labels:
    app: sc4snmp-autodiscovery-simulator
    agent-id: ${name}
    variation: ${variation}
    range-variation: ${range_variation}
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
          exec snmpsimd.py ${extra_flags}
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
        name: ${configmap}
YAML
}

start_docker_agents() {
  local ordinal
  local name
  local network
  local old_container
  local -a old_containers=()
  local -a attached_containers=()

  CURRENT_STAGE="Deploying Docker-backed SNMP simulators"
  echo $(green "[STEP] ${CURRENT_STAGE}")
  echo $(green "[INFO] Creating 18 static-IP agents on Docker networks ${DOCKER_NETWORK_V1} and ${DOCKER_NETWORK_V2}")
  mapfile -t old_containers < <(
    sudo docker ps -aq --filter label=sc4snmp.integration.autodiscovery=true
  )
  if (( ${#old_containers[@]} > 0 )); then
    sudo docker rm -f "${old_containers[@]}" >/dev/null
  fi
  for network in "${DOCKER_NETWORK_V1}" "${DOCKER_NETWORK_V2}"; do
    if sudo docker network inspect "${network}" >/dev/null 2>&1; then
      mapfile -t attached_containers < <(
        sudo docker network inspect "${network}" \
          --format '{{range .Containers}}{{.Name}}{{"\n"}}{{end}}'
      )
      for old_container in "${attached_containers[@]}"; do
        [[ -n "${old_container}" ]] || continue
        sudo docker network disconnect -f "${network}" "${old_container}"
      done
      sudo docker network rm "${network}" >/dev/null
    fi
  done
  sudo docker network create --driver bridge \
    --subnet "${V1_CIDR}" --gateway "${V1_DOCKER_GATEWAY}" \
    "${DOCKER_NETWORK_V1}" >/dev/null
  sudo docker network create --driver bridge \
    --subnet "${V2_CIDR}" --gateway "${V2_DOCKER_GATEWAY}" \
    "${DOCKER_NETWORK_V2}" >/dev/null

  for ordinal in $(seq 1 9); do
    name="$(printf 'snmp-agent-v1-%03d' "${ordinal}")"
    start_docker_agent \
      "${name}" "10.1.1.${ordinal}" v2c v1 "${DOCKER_NETWORK_V1}" \
      "${DATA_ROOT}/v2c" \
      "--v2c-arch --data-dir=/usr/local/snmpsim/data"
  done

  for ordinal in $(seq 1 5); do
    name="$(printf 'snmp-agent-v2-%03d' "${ordinal}")"
    start_docker_agent \
      "${name}" "10.2.2.${ordinal}" v3-sha v2 "${DOCKER_NETWORK_V2}" \
      "${DATA_ROOT}/v3-sha" \
      "--v3-only --v3-engine-id=${V3_SHA_ENGINE} --v3-context-engine-id=${V3_SHA_ENGINE} --v3-user=${V3_SHA_USER} --v3-auth-key=${V3_SHA_AUTH_KEY} --v3-auth-proto=SHA --v3-priv-key=${V3_SHA_PRIV_KEY} --v3-priv-proto=AES --data-dir=/usr/local/snmpsim/data"
  done

  for ordinal in $(seq 6 9); do
    name="$(printf 'snmp-agent-v2-%03d' "${ordinal}")"
    start_docker_agent \
      "${name}" "10.2.2.${ordinal}" v3-md5 v2 "${DOCKER_NETWORK_V2}" \
      "${DATA_ROOT}/v3-md5" \
      "--v3-only --v3-engine-id=${V3_MD5_ENGINE} --v3-context-engine-id=${V3_MD5_ENGINE} --v3-user=${V3_MD5_USER} --v3-auth-key=${V3_MD5_AUTH_KEY} --v3-auth-proto=MD5 --v3-priv-key=${V3_MD5_PRIV_KEY} --v3-priv-proto=AES --data-dir=/usr/local/snmpsim/data"
  done

  for ordinal in $(seq 1 9); do
    name="$(printf 'snmp-agent-v1-%03d' "${ordinal}")"
    verify_docker_agent_ip \
      "${name}" "${DOCKER_NETWORK_V1}" "10.1.1.${ordinal}"
  done
  for ordinal in $(seq 1 9); do
    name="$(printf 'snmp-agent-v2-%03d' "${ordinal}")"
    verify_docker_agent_ip \
      "${name}" "${DOCKER_NETWORK_V2}" "10.2.2.${ordinal}"
  done

  echo $(green "[DONE] Deployed 18 Docker simulator containers")
  echo $(green "[DONE] Docker reports all 18 requested simulator IPs exactly")
  echo $(green "[INFO] Docker simulator containers:")
  sudo docker ps \
    --filter label=sc4snmp.integration.autodiscovery=true \
    --format 'table {{.Names}}\t{{.Status}}\t{{.Networks}}'
}

start_microk8s_agents() {
  local ordinal
  local expected_ip
  local actual_ip
  local name
  local namespace_manifest

  command -v microk8s >/dev/null 2>&1 || {
    echo $(red "microk8s is required for the microk8s simulator backend") >&2
    exit 1
  }

  CURRENT_STAGE="Waiting for the MicroK8s API"
  echo $(green "[STEP] ${CURRENT_STAGE}")
  wait_for_microk8s_api 180 5

  CURRENT_STAGE="Preparing the MicroK8s simulator namespace"
  echo $(green "[STEP] ${CURRENT_STAGE}")
  echo $(green "[INFO] Creating or updating namespace ${SIMULATOR_NAMESPACE}")
  namespace_manifest="$(kctl create namespace "${SIMULATOR_NAMESPACE}" \
    --dry-run=client -o yaml)"
  apply_k8s_manifest "namespace ${SIMULATOR_NAMESPACE}" <<< "${namespace_manifest}"
  kctl delete deployment,service,pod,networkpolicy \
    -n "${SIMULATOR_NAMESPACE}" \
    -l sc4snmp.integration.autodiscovery=true \
    --ignore-not-found=true
  assert_simulator_ips_available
  echo $(green "[DONE] Namespace ${SIMULATOR_NAMESPACE} is ready")

  CURRENT_STAGE="Preparing static Calico simulator ranges"
  echo $(green "[STEP] ${CURRENT_STAGE}")
  kctl get crd ippools.crd.projectcalico.org >/dev/null
  ensure_calico_pool_for_range \
    sc4snmp-autodiscovery-v1-pool "${V1_CIDR}" 10.1.1.1 10.1.1.9
  ensure_calico_pool_for_range \
    sc4snmp-autodiscovery-v2-pool "${V2_CIDR}" 10.2.2.1 10.2.2.9
  echo $(green "[DONE] Static simulator ranges are available through Calico")

  CURRENT_STAGE="Loading compact SNMP simulator data"
  echo $(green "[STEP] ${CURRENT_STAGE}")
  echo $(green "[INFO] Creating v2c, v3 SHA/AES, and v3 MD5/AES ConfigMaps")
  create_simulator_configmap \
    autodiscovery-v2c-data public.snmprec \
    "${DATA_ROOT}/v2c/public.snmprec"
  create_simulator_configmap \
    autodiscovery-v3-sha-data 1.3.6.1.6.1.1.0.snmprec \
    "${DATA_ROOT}/v3-sha/1.3.6.1.6.1.1.0.snmprec"
  create_simulator_configmap \
    autodiscovery-v3-md5-data 1.3.6.1.6.1.1.0.snmprec \
    "${DATA_ROOT}/v3-md5/1.3.6.1.6.1.1.0.snmprec"
  echo $(green "[DONE] Loaded three simulator data ConfigMaps into ${SIMULATOR_NAMESPACE}")

  CURRENT_STAGE="Deploying MicroK8s SNMP simulators"
  echo $(green "[STEP] ${CURRENT_STAGE}")
  echo $(green "[INFO] Creating 18 static Pods in ${SIMULATOR_NAMESPACE}")
  for ordinal in $(seq 1 9); do
    name="$(printf 'snmp-agent-v1-%03d' "${ordinal}")"
    deploy_k8s_agent \
      "${name}" "10.1.1.${ordinal}" v2c v1 autodiscovery-v2c-data \
      "--v2c-arch --data-dir=/usr/local/snmpsim/data"
  done
  for ordinal in $(seq 1 5); do
    name="$(printf 'snmp-agent-v2-%03d' "${ordinal}")"
    deploy_k8s_agent \
      "${name}" "10.2.2.${ordinal}" v3-sha v2 autodiscovery-v3-sha-data \
      "--v3-only --v3-engine-id=${V3_SHA_ENGINE} --v3-context-engine-id=${V3_SHA_ENGINE} --v3-user=${V3_SHA_USER} --v3-auth-key=${V3_SHA_AUTH_KEY} --v3-auth-proto=SHA --v3-priv-key=${V3_SHA_PRIV_KEY} --v3-priv-proto=AES --data-dir=/usr/local/snmpsim/data"
  done
  for ordinal in $(seq 6 9); do
    name="$(printf 'snmp-agent-v2-%03d' "${ordinal}")"
    deploy_k8s_agent \
      "${name}" "10.2.2.${ordinal}" v3-md5 v2 autodiscovery-v3-md5-data \
      "--v3-only --v3-engine-id=${V3_MD5_ENGINE} --v3-context-engine-id=${V3_MD5_ENGINE} --v3-user=${V3_MD5_USER} --v3-auth-key=${V3_MD5_AUTH_KEY} --v3-auth-proto=MD5 --v3-priv-key=${V3_MD5_PRIV_KEY} --v3-priv-proto=AES --data-dir=/usr/local/snmpsim/data"
  done

  kctl wait --for=condition=Ready pod \
    -n "${SIMULATOR_NAMESPACE}" \
    -l sc4snmp.integration.autodiscovery=true \
    --timeout=300s
  echo $(green "[DONE] All 18 simulator Pods are ready")

  echo $(green "[INFO] Running: microk8s kubectl get pods -n ${SIMULATOR_NAMESPACE} -o wide")
  kctl get pods \
    -n "${SIMULATOR_NAMESPACE}" \
    -l sc4snmp.integration.autodiscovery=true \
    -o wide
  for ordinal in $(seq 1 9); do
    name="$(printf 'snmp-agent-v1-%03d' "${ordinal}")"
    expected_ip="10.1.1.${ordinal}"
    actual_ip="$(kctl get pod "${name}" -n "${SIMULATOR_NAMESPACE}" \
      -o jsonpath='{.status.podIP}')"
    [[ "${actual_ip}" == "${expected_ip}" ]] || {
      echo $(red "Pod ${name} expected ${expected_ip}, received ${actual_ip}") >&2
      exit 1
    }
  done
  for ordinal in $(seq 1 9); do
    name="$(printf 'snmp-agent-v2-%03d' "${ordinal}")"
    expected_ip="10.2.2.${ordinal}"
    actual_ip="$(kctl get pod "${name}" -n "${SIMULATOR_NAMESPACE}" \
      -o jsonpath='{.status.podIP}')"
    [[ "${actual_ip}" == "${expected_ip}" ]] || {
      echo $(red "Pod ${name} expected ${expected_ip}, received ${actual_ip}") >&2
      exit 1
    }
  done
  echo $(green "[DONE] Kubernetes reports all 18 requested simulator Pod IPs exactly")
}

if [[ "${BACKEND_MODE}" == "microk8s" ]]; then
  start_microk8s_agents
else
  start_docker_agents
fi

echo $(green "[DONE] Simulator backend ready: ${BACKEND_MODE}")
echo $(green "[INFO] v1 range: 9 agents -> $(format_ips "${V2C_IPS[@]}")")
echo $(green "[INFO] v2 range: 9 agents -> $(format_ips "${V3_SHA_IPS[@]}" "${V3_MD5_IPS[@]}")")
echo $(green "[INFO] integration_v2c: 9 agents -> $(format_ips "${V2C_IPS[@]}")")
echo $(green "[INFO] integration_v3_sha: 5 agents -> $(format_ips "${V3_SHA_IPS[@]}")")
echo $(green "[INFO] integration_v3_md5: 4 agents -> $(format_ips "${V3_MD5_IPS[@]}")")

CURRENT_STAGE="Configuring Nginx simulator health proxies"
echo $(green "[STEP] ${CURRENT_STAGE}")
echo $(green "[INFO] Discovery uses the simulator IPs directly; Nginx provides one health endpoint per SNMP variation")
{
  echo "upstream autodiscovery_v2c_agents {"
  for ip in "${V2C_IPS[@]}"; do
    echo "    server ${ip}:161;"
  done
  echo "}"
  echo "upstream autodiscovery_v3_sha_agents {"
  for ip in "${V3_SHA_IPS[@]}"; do
    echo "    server ${ip}:161;"
  done
  echo "}"
  echo "upstream autodiscovery_v3_md5_agents {"
  for ip in "${V3_MD5_IPS[@]}"; do
    echo "    server ${ip}:161;"
  done
  echo "}"
  echo "server { listen 127.0.0.1:${NGINX_V2C_PORT} udp; proxy_timeout 3s; proxy_responses 1; proxy_pass autodiscovery_v2c_agents; }"
  echo "server { listen 127.0.0.1:${NGINX_V3_SHA_PORT} udp; proxy_timeout 3s; proxy_responses 1; proxy_pass autodiscovery_v3_sha_agents; }"
  echo "server { listen 127.0.0.1:${NGINX_V3_MD5_PORT} udp; proxy_timeout 3s; proxy_responses 1; proxy_pass autodiscovery_v3_md5_agents; }"
} | sudo tee "${NGINX_STREAM_CONFIG}" >/dev/null

EXPECTED_ROUTE_COUNT=3
CONFIGURED_ROUTE_COUNT="$(grep -c '^server {' "${NGINX_STREAM_CONFIG}")"
if [[ "${CONFIGURED_ROUTE_COUNT}" -ne "${EXPECTED_ROUTE_COUNT}" ]]; then
  echo $(red "Nginx route configuration failed: expected ${EXPECTED_ROUTE_COUNT}, configured ${CONFIGURED_ROUTE_COUNT}") >&2
  exit 1
fi
echo $(green "[DONE] Generated ${CONFIGURED_ROUTE_COUNT}/${EXPECTED_ROUTE_COUNT} Nginx UDP routes")

sudo tee "${NGINX_CONFIG}" >/dev/null <<EOF
include /etc/nginx/modules-enabled/*.conf;
user www-data;
worker_processes 1;
pid /run/sc4snmp-autodiscovery-nginx.pid;
error_log /var/log/nginx/sc4snmp-autodiscovery-error.log;
events { worker_connections 256; }
stream { include ${NGINX_STREAM_CONFIG}; }
EOF

sudo tee "/etc/systemd/system/${NGINX_SERVICE}" >/dev/null <<EOF
[Unit]
Description=SC4SNMP autodiscovery integration Nginx UDP proxy
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
ExecStartPre=/usr/sbin/nginx -t -q -c ${NGINX_CONFIG}
ExecStart=/usr/sbin/nginx -c ${NGINX_CONFIG} -g "daemon off;"
ExecReload=/usr/sbin/nginx -s reload -c ${NGINX_CONFIG}
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

sudo nginx -t -c "${NGINX_CONFIG}"
sudo systemctl daemon-reload
sudo systemctl enable "${NGINX_SERVICE}"
sudo systemctl restart "${NGINX_SERVICE}"
sudo systemctl is-active --quiet "${NGINX_SERVICE}"
echo $(green "[DONE] Nginx proxy service restarted successfully: ${NGINX_SERVICE}")
echo $(green "[INFO] Nginx health proxies loaded: ${CONFIGURED_ROUTE_COUNT}/${EXPECTED_ROUTE_COUNT}")

verify_agent() {
  local address="$1"
  local variation="$2"
  local agent_name="$3"
  local attempt

  for attempt in $(seq 1 20); do
    if [[ "$variation" == "v2c" ]]; then
      if snmpget -v2c -c public -On "${address}:161" \
          1.3.6.1.2.1.1.1.0 >/dev/null 2>&1; then
        return 0
      fi
    elif [[ "${BACKEND_MODE}" == "docker" ]] &&
      [[ "$(sudo docker inspect -f '{{.State.Running}}' "$agent_name" 2>/dev/null)" == "true" ]] &&
      sudo docker logs "$agent_name" 2>&1 | grep -q "Listening at UDP/IPv4 endpoint 0.0.0.0:161"; then
      # Net-SNMP clients are not wire-compatible with every privacy mode in
      # this older simulator image. The PySNMP integration test performs the
      # authenticated multi-OID v3 query after the application environment is
      # installed; here we only gate startup and endpoint readiness.
      return 0
    elif [[ "${BACKEND_MODE}" == "microk8s" ]] &&
      [[ "$(kctl get pod "$agent_name" \
        -n "${SIMULATOR_NAMESPACE}" \
        -o jsonpath='{.status.phase}' 2>/dev/null)" == "Running" ]]; then
      return 0
    fi
    sleep 1
  done
  echo $(red "Simulator ${address}:161 (${variation}) did not become ready") >&2
  return 1
}

for ordinal in $(seq 1 9); do
  agent_name="$(printf 'snmp-agent-v1-%03d' "${ordinal}")"
  verify_agent "10.1.1.${ordinal}" v2c "${agent_name}"
done
for ordinal in $(seq 1 5); do
  agent_name="$(printf 'snmp-agent-v2-%03d' "${ordinal}")"
  verify_agent "10.2.2.${ordinal}" v3-sha "${agent_name}"
done
for ordinal in $(seq 6 9); do
  agent_name="$(printf 'snmp-agent-v2-%03d' "${ordinal}")"
  verify_agent "10.2.2.${ordinal}" v3-md5 "${agent_name}"
done

snmpget -v2c -c public -On "127.0.0.1:${NGINX_V2C_PORT}" \
  1.3.6.1.2.1.1.1.0 >/dev/null
echo $(green "[DONE] Nginx v2c health proxy returned an SNMP response")

CURRENT_STAGE="Reporting autodiscovery simulator readiness"
echo $(green "[STEP] ${CURRENT_STAGE}")
echo $(green "[DONE] integration_v2c: 9/9 agents ready -> $(format_ips "${V2C_IPS[@]}")")
echo $(green "[DONE] integration_v3_sha: 5/5 agents ready -> $(format_ips "${V3_SHA_IPS[@]}")")
echo $(green "[DONE] integration_v3_md5: 4/4 agents ready -> $(format_ips "${V3_MD5_IPS[@]}")")
echo $(green "[DONE] v1 range: 9/9 actual simulator IPs ready")
echo $(green "[DONE] v2 range: 9/9 actual simulator IPs ready")
echo $(green "[DONE] Autodiscovery environment ready: 18/18 agents available using ${BACKEND_MODE} backend")
