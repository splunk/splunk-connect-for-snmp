#!/bin/bash

install_basic_software() {
  commands=("sudo snap install microk8s --classic" \
    "sudo microk8s status --wait-ready"  \
    "sudo microk8s enable dns helm3" \
    "sudo snap install docker" "sudo apt-get install snmp -y" \
    "nohup sudo docker run -p161:161/udp tandrup/snmpsim > /dev/null 2>&1 &" \
    "snmpget -v1 -c public 127.0.0.1 1.3.6.1.2.1.1.1.0")
  for command in "${commands[@]}" ; do
    if ! ${command} ; then
      echo "error when executing ${command}"
      exit 1
    fi
  done
}

deploy_kubernetes() {
  echo "For now I don't do anything"
}

install_basic_software
deploy_kubernetes