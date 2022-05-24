#!/bin/bash

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

wait_for_splunk() {
  while [ "$(sudo docker ps | grep "splunk:latest" | grep healthy)" == "" ] ; do
    echo $(yellow "Waiting for Splunk initialization")
    sleep 1
  done
}

function define_python() {
  if command -v python &> /dev/null; then
      PYTHON=python
  elif command -v python3 &> /dev/null; then
      PYTHON=python3
  else
    echo $(red "Cannot find python command")
    exit 1
  fi
}

deploy_poetry() {
  sudo apt -y install python3-venv
  curl -sSL https://install.python-poetry.org | $PYTHON -
  export PATH="/home/ubuntu/.local/bin:$PATH"
  poetry install
  poetry add -D splunk-sdk
  poetry add -D splunklib
  poetry add -D pysnmp
}

wait_for_pod_initialization() {
  while [ "$(sudo microk8s kubectl get pod -n sc4snmp | grep ContainerCreating)" != "" ] ; do
    echo "Waiting for POD initialization..."
    sleep 1
  done
}

wait_for_rabbitmq_to_be_up() {
  while [ "$(sudo microk8s kubectl get pod -n sc4snmp | grep 0/1)" != "" ] ; do
    echo "Waiting for RabbitMQ POD initialization..."
    sleep 1
  done
}

sudo apt -y install docker.io
cd ~/splunk-connect-for-snmp

echo $(green "Building Docker image")

sudo docker build -t snmp-local .

sudo docker save snmp-local > myimage.tar
sudo microk8s ctr image import myimage.tar

sudo docker pull splunk/splunk:latest
echo $(green "Running Splunk in Docker")
sudo docker run -d -p 8000:8000 -p 8088:8088 -p 8089:8089 -e SPLUNK_START_ARGS='--accept-license' -e SPLUNK_PASSWORD='changeme2' splunk/splunk:latest

wait_for_splunk

cd integration_tests
chmod u+x prepare_splunk.sh
echo $(green "Preparing Splunk instance")
./prepare_splunk.sh
sed -i "s/###SPLUNK_TOKEN###/$(cat hec_token)/" values.yaml
sed -i "s/###LOAD_BALANCER_ID###/$(hostname -I | cut -d " " -f1)/" values.yaml
sudo docker run -d -p 161:161/udp tandrup/snmpsim

sudo microk8s enable helm3
sudo microk8s enable storage
sudo microk8s enable dns
sudo microk8s enable rbac
sudo microk8s enable community
sudo microk8s enable openebs
sudo systemctl enable iscsid
yes $(hostname -I | cut -d " " -f1)/32 | sudo microk8s enable metallb

cd ~/splunk-connect-for-snmp/charts/splunk-connect-for-snmp
microk8s helm3 dep update
cd ~/splunk-connect-for-snmp/integration_tests

echo $(green "Installing SC4SNMP on Kubernetes")
sudo microk8s helm3 install snmp -f values.yaml ~/splunk-connect-for-snmp/charts/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace

wait_for_pod_initialization
wait_for_rabbitmq_to_be_up

define_python

deploy_poetry

poetry run pytest --splunk_host="localhost" --splunk_password="changeme2" \
  --trap_external_ip="$(hostname -I | cut -d " " -f1)" --junitxml=result.xml > pytest.log

if [ ! -z "${S3_PATH}" ]; then
  aws s3 cp /home/ubuntu/splunk-connect-for-snmp/integration_tests/result.xml s3://snmp-integration-tests/$S3_PATH/
  aws s3 cp /home/ubuntu/splunk-connect-for-snmp/integration_tests/pytest.log s3://snmp-integration-tests/$S3_PATH/
fi
