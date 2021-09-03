#!/bin/bash

SPLUNK_SECRET_NAME=remote-splunk

install_simulator() {
  simulator=$(nohup sudo docker run -p161:161/udp tandrup/snmpsim > /dev/null 2>&1 &)
  if ! $simulator ; then
    echo "Cannot start SNMP simulator"
    exit 2
  fi

  echo "Sample SNMP get from the simulator"
  snmpget -v1 -c public 127.0.0.1 1.3.6.1.2.1.1.1.0
}

create_splunk_secret() {
  splunk_ip=$1

  delete_secret=$(microk8s.kubectl delete secret "${SPLUNK_SECRET_NAME}" 2>&1)
  echo "I have tried to remove ${SPLUNK_SECRET_NAME} and I got ${delete_secret}"

  secret_created=$(microk8s.kubectl create secret generic "${SPLUNK_SECRET_NAME}" \
   --from-literal=SPLUNK_HEC_URL=https://"${splunk_ip}":8088/services/collector \
   --from-literal=SPLUNK_HEC_TLS_SKIP_VERIFY=true \
   --from-literal=SPLUNK_HEC_TOKEN=00000000-0000-0000-0000-000000000000 2>&1)
  echo "Secret created: ${secret_created}"
}

create_splunk_indexes() {
  splunk_ip=$1
  splunk_password=$2
  index_names=("em_metrics" "em_meta" "em_logs")
  index_types=("metric" "event" "event")
  for index in "${!index_names[@]}" ; do
    if ! curl -k -u admin:"${splunk_password}" "https://${splunk_ip}:8089/services/data/indexes" \
      -d datatype="${index_types[${index}]}" -d name="${index_names[${index}]}" ; then
      echo "Error when creating ${index_names[${index}]} of type ${index_types[${index}]}"
    fi
  done
}

docker0_ip() {
  valid_snmp_get_ip=$(ip --brief address show | grep "^docker0" | \
    sed -e 's/[[:space:]]\+/|/g' | cut -d\| -f3 | cut -d/ -f1)
  if [ "${valid_snmp_get_ip}" == "" ] ; then
    echo "Error, cannot get a valid IP that will be used for querying the SNMP simulator"
    exit 4
  fi

  echo "${valid_snmp_get_ip}"
}

wait_for_load_balancer_external_ip() {
  while [ "$(microk8s.kubectl get service/sc4-snmp-traps -n sc4snmp | grep pending)" != "" ] ; do
    echo "Waiting for service/sc4-snmp-traps to have a proper external IP..."
    sleep 1
  done

  while [ "$(microk8s.kubectl get pod -n sc4snmp | grep ContainerCreating)" != "" ] ; do
    echo "Waiting for POD initialization..."
    sleep 1
  done
}

update_scheduler_inventory() {
  valid_snmp_get_ip=$1
  # These extra spaces are required to fit the structure in scheduler-config.yaml
  scheduler_config=$(cat << EOF
    ${valid_snmp_get_ip}:161,2c,public,basev1,1
EOF
)
  scheduler_config=$(echo "${scheduler_config}" | \
    cat ./deploy/sc4snmp/ftr/scheduler-inventory.yaml - | microk8s.kubectl apply -n sc4snmp -f -)
  echo "${scheduler_config}"
}

stop_simulator() {
  id=$(sudo docker ps --filter ancestor=tandrup/snmpsim --format "{{.ID}}")
  echo "Trying to stop docker container $id"

  commands=("sudo docker stop $id" "sudo docker rm $id")
  for command in "${commands[@]}" ; do
    if ! ${command} ; then
      echo "Error when executing ${command}"
    fi
  done
}

deploy_poetry() {
  curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python -
  source "$HOME"/.poetry/env
  poetry install
  poetry add -D splunk-sdk
  poetry add -D splunklib
  poetry add -D pysnmp
}

run_integration_tests() {
  splunk_ip=$1
  splunk_password=$2

  trap_external_ip=$(microk8s.kubectl -n sc4snmp get service/sc4-snmp-traps | \
    tail -1 | sed -e 's/[[:space:]]\+/\t/g' | cut -f4)

  deploy_poetry
  poetry run pytest --splunk_host="$splunk_ip" --splunk_password="$splunk_password" \
    --trap_external_ip="${trap_external_ip}"
}

post_installation_kubernetes_config() {
  microk8s.status --wait-ready
  microk8s.enable dns helm3 metallb:10.1.1.1-196.255.255.255
}

fix_local_settings() {
  # CentOS 7 has LANG set by default to C.UTF-8, and Python doesn't like it
  # Ubuntu (any version), and CentOS 8 are just fine
  export LC_ALL=en_US.UTF-8
  export LANG=en_US.UTF-8
}

full_kubernetes_deployment() {
  splunk_ip=$1
  splunk_password=$2
  valid_snmp_get_ip=$3

  create_splunk_indexes "$splunk_ip" "$splunk_password"
  curl -sfL https://raw.githubusercontent.com/splunk/splunk-connect-for-snmp/main/deploy/install.bash  | \
    MODE=splunk \
    PROTO=https \
    INSECURE_SSL=true \
    HOST="$splunk_ip" \
    PORT=8088 \
    TOKEN=00000000-0000-0000-0000-000000000000 \
    METRICS_INDEX=em_metrics \
    EVENTS_INDEX=em_logs \
    META_INDEX=em_meta \
    CLUSTER_NAME=foo \
    SHAREDIP=$(hostname -I | cut -d ' ' -f 1)/32 \
    RESOLVERIP=8.8.4.4 \
    sudo -E bash -

    wait_for_load_balancer_external_ip
    update_scheduler_inventory "${valid_snmp_get_ip}"
}
# ------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------

while getopts u:p: flag
do
    case "${flag}" in
        u) splunk_url=${OPTARG} ;;
        p) splunk_password=${OPTARG} ;;
    esac
done
if [ "$splunk_url" == "" ] || [ "$splunk_password" == "" ] ; then
  echo "Splunk URL or Splunk Password cannot be empty"
  echo "Help: deploy_and_test.sh -u <splunk_url> -p <splunk_password>"
  exit 1
fi

post_installation_kubernetes_config
fix_local_settings
install_simulator
trap_external_ip=$(docker0_ip)
full_kubernetes_deployment "$splunk_url" "$splunk_password" "$trap_external_ip"
microk8s.kubectl config set-context --current --namespace=sc4snmp
run_integration_tests "$splunk_url" "$splunk_password"