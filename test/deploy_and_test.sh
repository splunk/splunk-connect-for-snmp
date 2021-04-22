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
  index_names=("netops" "snmp" "snmp_metric")
  for index_name in "${index_names[@]}" ; do
    if ! curl -k -u admin:"${splunk_password}" "https://${splunk_ip}:8089/services/data/indexes" \
      -d datatype=event -d name="${index_name}" ; then
      echo "Error when creating ${index_name}"
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

deploy_kubernetes() {
  splunk_ip=$1
  splunk_password=$2
  valid_snmp_get_ip=$3

  create_splunk_secret "$splunk_ip"
  create_splunk_indexes "$splunk_ip" "$splunk_password"
  # These extra spaces are required to fit the structure in scheduler-config.yaml
  scheduler_config=$(echo "    ${valid_snmp_get_ip}:161,2c,public,1.3.6.1.2.1.1.1.0,1" | \
    cat ../deploy/sc4snmp/scheduler-config.yaml - | microk8s.kubectl apply -f -)
  echo "${scheduler_config}"

  result=$(cat ../deploy/sc4snmp/traps-service.yaml  | \
    sed "s/loadBalancerIP: replace-me/loadBalancerIP: ${valid_snmp_get_ip}/" | microk8s.kubectl apply -f -)
  echo "${result}"

  for f in $(ls ../deploy/sc4snmp/*.yaml | grep -v "scheduler-config\|traps-service"); do
    echo "Deploying $f"
    if ! microk8s.kubectl apply -f "$f" ; then
      echo "Error when deploying $f"
    fi
  done
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

stop_everything() {
  stop_simulator
  if ! microk8s.kubectl delete secret "${SPLUNK_SECRET_NAME}" ; then
    echo "Error when deleting ${SPLUNK_SECRET_NAME}"
  fi
  for f in ../deploy/sc4snmp/*.yaml ; do
    echo "Undeploying $f"
    if ! microk8s.kubectl delete -f "$f" ; then
      echo "Error when deploying $f"
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

  trap_external_ip=$(microk8s.kubectl get service/sc4-snmp-traps | \
    tail -1 | sed -e 's/[[:space:]]\+/\t/g' | cut -f4)

  deploy_poetry
  poetry run pytest --splunk_host="$splunk_ip" --splunk_password="$splunk_password" \
    --trap_external_ip="${trap_external_ip}"
  echo "Press ENTER to undeploy everything" && read -r dummy
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
if [ "$splunk_url" == "" ] || [ "splunk_password" == "" ] ; then
  echo "Splunk URL or Splunk Password cannot be empty"
  echo "Help: deploy_and_test.sh -u <splunk_url> -p <splunk_password>"
  exit 1
fi

post_installation_kubernetes_config
fix_local_settings
install_simulator
trap_external_ip=$(docker0_ip)
deploy_kubernetes "$splunk_url" "$splunk_password" "$trap_external_ip"
run_integration_tests "$splunk_url" "$splunk_password"
stop_everything

