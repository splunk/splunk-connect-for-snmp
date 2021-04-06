#!/bin/sh

echo "      [.. ..      [..                 [.. ..  [...     [..[..       [..[.......   "
echo "    [..    [.. [..   [..      [..   [..    [..[. [..   [..[. [..   [...[..    [.. "
echo "     [..      [..           [ [..    [..      [.. [..  [..[.. [.. [ [..[..    [.. "
echo "       [..    [..          [. [..      [..    [..  [.. [..[..  [..  [..[.......   "
echo "          [.. [..        [..  [..         [.. [..   [. [..[..   [.  [..[..        "
echo "    [..    [.. [..   [..[.... [. [..[..    [..[..    [. ..[..       [..[..        "
echo "      [.. ..     [....        [..     [.. ..  [..      [..[..       [..[..        "



KUBERNETES_POLLER_CONFIG_MAP_NAME="poller-config"
SC4SNMP_POLLER_DIR="./sc4snmp/"
SC4SNMP_TRAP_DIR="./sc4snmp/"

# Change this as needed to adjust with your flavor of k8s wrapper! i.e. kubectl k3s minikube
alias k='k3s kubectl'
# alias k='minikube kubectl'


kubernetes_undeploy_all() {

  for conf in "$@"; do
    k delete -f "${conf}"

  done

    # Hard Clean up
    k delete deployment sc4-snmp-traps
    k delete service/sc4-snmp-traps-service

    k delete deployment mib-server
    k delete service/mib-server-service

    # k -n default  delete pod,svc,deployment --all   --grace-period 0  --force --v=6 && sleep 3 && kubectl get pods
    k -n default delete pod,svc,deployment --all   --grace-period 0  --force && sleep 3 && kubectl get pods
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
  k apply configmap "${kubernetes_configmap_name}" --from-file="${poller_config_file}" --dry-run=client -o yaml \
    | k apply -f -
  k get configmap "${kubernetes_configmap_name}" -o yaml
}

kubernetes_create_or_replace_docker_secret() {
  server=$1
  username=$2
  authentication_token=$3
  email=$4
  secret_name=$5

  k delete secret "${secret_name}"
  k create secret docker-registry "${secret_name}" \
    --docker-server="${server}" \
    --docker-username="${username}" \
    --docker-password="${authentication_token}" \
    --docker-email="${email}"
}

kubernetes_create_or_replace_hec_secret() {
  echo "== kubernetes_create_or_replace_hec_secret =="
  url=$1
  hec_token=$2
  secret_name=$3

  k delete secret "${secret_name}"
  k create secret generic remote-splunk \
    --from-literal=SPLUNK_HEC_URL="${url}" \
    --from-literal=SPLUNK_HEC_TLS_VERIFY=true \
    --from-literal=SPLUNK_HEC_TOKEN="${hec_token}"
  k get secret
}

clean_up() {
  echo "== clean_up =="
  for temporary_file in "$@"; do
    rm -rf "${temporary_file}"
  done
}

undeploy_poller() {
  rabbitmq_deployment="deployment.apps/$(yq -r .metadata.name $SC4SNMP_POLLER_DIR\rq-deployment.yaml)"
  echo "Removing deployment for ${rabbitmq_deployment}"
  k delete "${rabbitmq_deployment}"

  rabbitmq_service="service/$(yq -r .metadata.name $SC4SNMP_POLLER_DIR/rq-service.yaml)"
  echo "Removing service ${rabbitmq_service}"
  k delete "${rabbitmq_service}"
}

kubernetes_deploy_rabbitmq() {
  k apply -f $SC4SNMP_POLLER_DIR/rq-deployment.yaml
  k apply -f $SC4SNMP_POLLER_DIR/rq-service.yaml
}

kubernetes_deploy_mongo() {
  k apply -f $SC4SNMP_POLLER_DIR/mongo-deployment.yaml
  k apply -f $SC4SNMP_POLLER_DIR/mongo-service.yaml
}

kubernetes_deploy_poller() {
  k apply -f $SC4SNMP_POLLER_DIR/scheduler-config.yaml
  k apply -f $SC4SNMP_POLLER_DIR/scheduler-deployment.yaml
  k apply -f $SC4SNMP_POLLER_DIR/worker-deployment.yaml
}

kubernetes_deploy_mibserver() {
  k apply -f $SC4SNMP_POLLER_DIR/mib-server-deployment.yaml
  k apply -f $SC4SNMP_POLLER_DIR/mib-server-service.yaml
}

kubernetes_deploy_snmpsim() {
  k apply -f $SC4SNMP_POLLER_DIR/sim-deployment.yaml
}

kubernetes_deploy_traps() {
  k apply -f $SC4SNMP_TRAP_DIR/traps-server-config.yaml
  k apply -f $SC4SNMP_TRAP_DIR/traps-deployment.yaml
  k apply -f $SC4SNMP_TRAP_DIR/traps-service.yaml
}

kubernetes_deploy_otel() {
  k apply -f $SC4SNMP_TRAP_DIR/otel-config.yaml
  k apply -f $SC4SNMP_TRAP_DIR/otel-deployment.yaml
  k apply -f $SC4SNMP_TRAP_DIR/otel-service.yaml
}




health_check() {
  echo "== health_check =="
  k get pods
  k get service
  k get deployment
  k get secret
}


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

kubernetes_undeploy_all $SC4SNMP_POLLER_DIR/worker-deployment.yaml $SC4SNMP_POLLER_DIR/scheduler-deployment.yaml \
  $SC4SNMP_POLLER_DIR/mongo-deployment.yaml $SC4SNMP_POLLER_DIR/mongo-service.yaml \
  $SC4SNMP_POLLER_DIR/rq-deployment.yaml $SC4SNMP_POLLER_DIR/rq-service.yaml \
  $SC4SNMP_POLLER_DIR/mib-server-deployment.yaml $SC4SNMP_POLLER_DIR/mib-server-service.yaml \
  $SC4SNMP_TRAP_DIR/traps-deployment.yaml $SC4SNMP_TRAP_DIR/traps-service.yaml \
  $SC4SNMP_TRAP_DIR/otel-deployment.yaml $SC4SNMP_TRAP_DIR/otel-deployment.yaml


health_check
sleep 5

github_username="${USER}"
github_email="${github_username}@splunk.com"
echo "Please type your person access github token:"
read -r token

poller_config_file=$(download_poller_config_file "${token}")

kubernetes_poller_deploy_or_update_config "${poller_config_file}" "${KUBERNETES_POLLER_CONFIG_MAP_NAME}"
# TODO: try to get the secret name with yq directly from scheduler-deployment.yaml. For now I am
# getting a syntax error when trying to access a list, not sure why.
kubernetes_create_or_replace_docker_secret "https://ghcr.io/v2/splunk" ${github_username} ${token} ${github_email} "regcred"
kubernetes_create_or_replace_hec_secret "https://54.145.16.74:8088/services/collector" "a43a5b69-1813-44a8-b9df-3b05ca84883d" "remote-splunk"


  echo "== kubernetes_deploy_snmpsim =="

kubernetes_deploy_snmpsim

  echo "== deploy remaining services =="
kubernetes_deploy_rabbitmq
kubernetes_deploy_mongo
kubernetes_deploy_mibserver
kubernetes_deploy_otel
sleep 3
kubernetes_deploy_traps
kubernetes_deploy_poller


clean_up "${poller_config_file}"
sleep 5
health_check
