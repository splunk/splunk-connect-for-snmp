#!/bin/bash

sudo apt -y install docker.io
cd ~/splunk-connect-for-snmp

sudo docker build -t snmp-local .

sudo docker save snmp-local > myimage.tar
sudo microk8s ctr image import myimage.tar

sudo docker pull splunk/splunk:latest
sudo docker run -d -p 8000:8000 -p 8088:8088 -p 8089:8089 -e SPLUNK_START_ARGS='--accept-license' -e SPLUNK_PASSWORD='changeme2' splunk/splunk:latest

cd integration_tests
chmod u+x prepare_splunk.sh
./prepare.splunk.sh
sed -i "s/###SPLUNK_TOKEN###/$(cat hec_token)/" values.yaml
sed -i "s/###LOAD_BALANCER_ID###/$(hostname -I | cut -d " " -f1)/" values.yaml
sudo docker run -d -p 161:161/udp tandrup/snmpsim

sudo microk8s enable helm3

cd ~/splunk-connect-for-snmp/charts/splunk-connect-for-snmp
microk8s helm3 dep update
cd ~/splunk-connect-for-snmp/integration_tests

sudo microk8s helm3 install snmp -f values.yaml ~/splunk-connect-for-snmp/charts/splunk-connect-for-snmp --namespace=sc4snmp --create-namespace
