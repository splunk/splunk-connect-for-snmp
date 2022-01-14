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
    echo $(yellow "Building Docker image")
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

sudo microk8s enable helm3 storage

cd ~/splunk-connect-for-snmp/charts/splunk-connect-for-snmp
microk8s helm3 dep update
cd ~/splunk-connect-for-snmp/integration_tests

echo $(green "Installing SC4SNMP on Kubernetes")
sudo microk8s helm3 install snmp -f values.yaml ~/splunk-connect-for-snmp/charts/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
