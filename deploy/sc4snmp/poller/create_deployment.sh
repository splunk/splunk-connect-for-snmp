#!/bin/sh

KUBERNETES_POLLER_CONFIG_MAP_NAME="poller-config"

download_poller_config_file() {
  token=$1
  poller_config_raw_file="raw.githubusercontent.com/splunk/splunk-connect-for-snmp-poller/main/config.yaml"
  full_poller_config_raw_file="https://${token}@${poller_config_raw_file}"
  poller_config_file_name="poller-config.yaml"
  if ! curl --fail -s "${full_poller_config_raw_file}" -o "${poller_config_file_name}" ; then
      echo "Cannot access ${poller_config_raw_file}"
      exit 1
  fi

  echo "${poller_config_file_name}"
}

kubernetes_poller_deploy_or_update_config() {
  poller_config_file=$1
  kubernetes_configmap_name=$2
  kubectl create configmap "${kubernetes_configmap_name}" --from-file="${poller_config_file}" --dry-run=client -o yaml \
    | kubectl apply -f -
  kubectl get configmap "${kubernetes_configmap_name}" -o yaml
}

clean_up() {
  for temporary_file in "$@"; do
    rm -rf "${temporary_file}"
  done
}

# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
echo "Please type your person access github token:"
read -r token
poller_config_file=$(download_poller_config_file "${token}")
kubernetes_poller_deploy_or_update_config "${poller_config_file}" "${KUBERNETES_POLLER_CONFIG_MAP_NAME}"

clean_up "${poller_config_file}"
