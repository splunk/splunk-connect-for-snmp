#!/bin/bash

SPLUNK_SECRET_NAME=remote-splunk

install_basic_software() {
  commands=("sudo snap install microk8s --classic" \
    "sudo microk8s status --wait-ready"  \
    "sudo microk8s enable dns helm3" \
    "sudo snap install docker" "sudo apt-get install snmp -y")
  for command in "${commands[@]}" ; do
    if ! ${command} ; then
      echo "Error when executing ${command}"
      exit 1
    fi
  done
}

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

  delete_secret=$(sudo microk8s kubectl delete secret "${SPLUNK_SECRET_NAME}" 2>&1)
  echo "I have tried to remove ${SPLUNK_SECRET_NAME} and I got ${delete_secret}"

  secret_created=$(sudo microk8s kubectl create secret generic "${SPLUNK_SECRET_NAME}" \
   --from-literal=SPLUNK_HEC_URL=https://"${splunk_ip}":8088/services/collector \
   --from-literal=SPLUNK_HEC_TLS_VERIFY=false \
   --from-literal=SPLUNK_HEC_TOKEN=00000000-0000-0000-0000-000000000000 2>&1)
  echo "Secret created: ${secret_created}"
}

deploy_kubernetes() {
  splunk_ip=$1

  valid_snmp_get_ip=$(ip --brief address show | grep "^docker0" | \
    sed -e 's/[[:space:]]\+/|/g' | cut -d\| -f3 | cut -d/ -f1)
  if [ "${valid_snmp_get_ip}" == "" ] ; then
    echo "Error, cannot get a valid IP that will be used for querying the SNMP simulator"
    exit 4
  fi

  create_splunk_secret "$splunk_ip"
  scheduler_config=$(echo "    ${valid_snmp_get_ip}:161,2c,public,1.3.6.1.2.1.1.1.0,1" | \
    cat ../deploy/sc4snmp/scheduler-config.yaml - | sudo microk8s kubectl apply -f1 -)
  echo "${scheduler_config}"

  for f in $(ls ../deploy/sc4snmp/*.yaml | grep -v scheduler-config); do
    echo "Deploying $f"
    if ! sudo microk8s kubectl apply -f "$f" ; then
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
  #microk8s kubectl delete secret "${SPLUNK_SECRET_NAME}"
}

echo "Provide splunk URL"
if ! read -r splunk_url ; then
  echo "Error when getting splunk URL"
  exit 3
fi

install_basic_software
install_simulator
deploy_kubernetes "$splunk_url"
stop_everything
