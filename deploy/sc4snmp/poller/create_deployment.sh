#!/bin/sh

KUBERNETES_POLLER_CONFIG_MAP_NAME="poller-config"

kubernetes_undeploy_all() {
  for conf in "$@"; do
    kubectl delete -f "${conf}"
  done
}

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

kubernetes_create_or_replace_docker_secret() {
  server=$1
  username=$2
  authentication_token=$3
  email=$4
  secret_name=$5

  kubectl delete secret "${secret_name}"
  kubectl create secret docker-registry "${secret_name}" \
    --docker-server="${server}" \
    --docker-username="${username}" \
    --docker-password="${authentication_token}" \
    --docker-email="${email}"
}

kubernetes_create_or_replace_hec_secret() {
  url=$1
  hec_token=$2
  secret_name=$3

  kubectl delete secret "${secret_name}"
  kubectl create secret generic remote-splunk \
    --from-literal=SPLUNK_HEC_URL="${url}" \
    --from-literal=SPLUNK_HEC_TLS_VERIFY=no \
    --from-literal=SPLUNK_HEC_TOKEN="${hec_token}"
}

clean_up() {
  for temporary_file in "$@"; do
    rm -rf "${temporary_file}"
  done
}

undeploy_poller() {
  rabbitmq_deployment="deployment.apps/$(yq -r .metadata.name rq-deployment.yaml)"
  echo "Removing deployment for ${rabbitmq_deployment}"
  kubectl delete "${rabbitmq_deployment}"

  rabbitmq_service="service/$(yq -r .metadata.name rq-service.yaml)"
  echo "Removing service ${rabbitmq_service}"
  kubectl delete "${rabbitmq_service}"
}

kubernetes_deploy_rabbitmq() {
  kubectl create -f rq-deployment.yaml
  kubectl create -f rq-service.yaml
}

kubernetes_deploy_mongo() {
  kubectl create -f mongo-deployment.yaml
  kubectl create -f mongo-service.yaml
}

kubernetes_deploy_poller() {
  kubectl create -f scheduler-deployment.yaml
  kubectl create -f worker-deployment.yaml
}

kubernetes_deploy_mibserver() {
  kubectl create -f mib-server-deployment.yaml
  kubectl create -f mib-server-service.yaml
}

health_check() {
  kubectl get pods
  kubectl get service
  kubectl get deployment
  kubectl get secret
}
# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

kubernetes_undeploy_all worker-deployment.yaml scheduler-deployment.yaml \
  mongo-deployment.yaml mongo-service.yaml \
  rq-deployment.yaml rq-service.yaml \
  mib-server-deployment.yaml mib-server-service.yaml
health_check

github_username="${USER}"
github_email="${github_username}@splunk.com"
echo "Please type your person access github token:"
read -r token
poller_config_file=$(download_poller_config_file "${token}")

kubernetes_poller_deploy_or_update_config "${poller_config_file}" "${KUBERNETES_POLLER_CONFIG_MAP_NAME}"
# TODO: try to get the secret name with yq directly from scheduler-deployment.yaml. For now I am
# getting a syntax error when trying to access a list, not sure why.
kubernetes_create_or_replace_docker_secret "https://ghcr.io/v2/splunk" ${github_username} ${token} ${github_email} "regcred"
kubernetes_create_or_replace_hec_secret "https://localhost:8000/services/collector" "12345678" "remote-splunk"
kubernetes_deploy_rabbitmq
kubernetes_deploy_mongo
kubernetes_deploy_mibserver
kubernetes_deploy_poller

clean_up "${poller_config_file}"
health_check
