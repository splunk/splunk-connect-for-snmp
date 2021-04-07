#!/bin/sh

deploy_kubernetes() {
  commands=("sudo snap install microk8s --classic" \
    "sudo microk8s status --wait-ready"  \
    "sudo microk8s enable dns helm3")
  for command in "${commands[@]}" ; do
    if ! ${command} ; then
      echo "error when executing ${command}"
      exit 1
    fi
  done
}

deploy_kubernetes