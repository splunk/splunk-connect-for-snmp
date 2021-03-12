#!/bin/sh

KUBERNETES_TRAP_CONFIG_MAP_NAME="trap-config"

kubernetes_undeploy_all() {
  k3s kubectl -n default  delete pod,svc,deployment --all   --grace-period 0  --force --v=6 && sleep 3 && kubectl get pods
  for conf in "$@"; do
    k3s kubectl delete -f "${conf}"

  done
}

download_trap_config_file() {
  token=$1
 trap_config_raw_file="raw.githubusercontent.com/splunk/splunk-connect-for-snmp-trap/main/config.yaml"
  full_trap_config_raw_file="https://${token}@${trap_config_raw_file}"
  trap_config_file_name="trap-config.yaml"
  if ! curl --fail -s "${full_trap_config_raw_file}" -o "${trap_config_file_name}" ; then
      echo "Cannot access ${trap_config_raw_file}"
      exit 1
  fi

  echo "${trap_config_file_name}"
}

kubernetes_trap_deploy_or_update_config() {
  trap_config_file=$1
  kubernetes_configmap_name=$2
  k3s kubectl create configmap "${kubernetes_configmap_name}" --from-file="${prap_config_file}" --dry-run=client -o yaml \
    | k3s kubectl apply -f -
  k3s kubectl get configmap "${kubernetes_configmap_name}" -o yaml
}

kubernetes_create_or_replace_docker_secret() {
  server=$1
  username=$2
  authentication_token=$3
  email=$4
  secret_name=$5

  k3s kubectl delete secret "${secret_name}"
  k3s kubectl create secret docker-registry "${secret_name}" \
    --docker-server="${server}" \
    --docker-username="${username}" \
    --docker-password="${authentication_token}" \
    --docker-email="${email}"
}

kubernetes_create_or_replace_hec_secret() {
  url=$1
  hec_token=$2
  secret_name=$3

  k3s kubectl delete secret "${secret_name}"
  k3s kubectl create secret generic remote-splunk \
    --from-literal=SPLUNK_HEC_URL="${url}" \
    --from-literal=SPLUNK_HEC_TLS_VERIFY=no \
    --from-literal=SPLUNK_HEC_TOKEN="${hec_token}"
}

clean_up() {
  for temporary_file in "$@"; do
    rm -rf "${temporary_file}"
  done
}

undeploy_trap() {
  rabbitmq_deployment="deployment.apps/$(yq -r .metadata.name rq-deployment.yaml)"
  echo "Removing deployment for ${rabbitmq_deployment}"
  k3s kubectl delete "${rabbitmq_deployment}"

  rabbitmq_service="service/$(yq -r .metadata.name rq-service.yaml)"
  echo "Removing service ${rabbitmq_service}"
  k3s kubectl delete "${rabbitmq_service}"
}

kubernetes_deploy_rabbitmq() {
  k3s kubectl create -f rq-deployment.yaml
  k3s kubectl create -f rq-service.yaml
}

kubernetes_deploy_mongo() {
  k3s kubectl create -f mongo-deployment.yaml
  k3s kubectl create -f mongo-service.yaml
}

kubernetes_deploy_mibserver() {
  k3s kubectl create -f mib-server-deployment.yaml
  k3s kubectl create -f mib-server-service.yaml
}

kubernetes_deploy_traps() {
  k3s kubectl create -f traps-deployment.yaml
  k3s kubectl create -f traps-service.yaml
}

health_check() {
  k3s kubectl get pods
  k3s kubectl get service
  k3s kubectl get deployment
  k3s kubectl get secret
}


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

kubernetes_undeploy_all worker-deployment.yaml scheduler-deployment.yaml \
  mongo-deployment.yaml mongo-service.yaml \
  rq-deployment.yaml rq-service.yaml \
  mib-server-deployment.yaml mib-server-service.yaml


k3s kubectl delete deployment sc4-snmp-traps
k3s kubectl delete service/sc4-snmp-traps-service

k3s kubectl delete deployment mib-server
k3s kubectl delete service/mib-server-service

health_check
sleep 5

github_username="${USER}"
github_email="${github_username}@splunk.com"
echo "Please type your person access github token:"
# read -r token
token=6b4885ba7c27556a7d3d30e06c1ac76843f7cc30
trap_config_file=$(download_trap_config_file "${token}")

kubernetes_trap_deploy_or_update_config "${trap_config_file}" "${KUBERNETES_TRAP_CONFIG_MAP_NAME}"
# TODO: try to get the secret name with yq directly from scheduler-deployment.yaml. For now I am
# getting a syntax error when trying to access a list, not sure why.
kubernetes_create_or_replace_docker_secret "https://ghcr.io/v2/splunk" ${github_username} ${token} ${github_email} "regcred"
kubernetes_create_or_replace_hec_secret "https://54.145.16.74:8088/services/collector" "a43a5b69-1813-44a8-b9df-3b05ca84883d" "remote-splunk"
kubernetes_deploy_rabbitmq
kubernetes_deploy_mongo
kubernetes_deploy_mibserver
kubernetes_deploy_traps

clean_up "${trap_config_file}"
health_check
