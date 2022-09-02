#!/bin/bash

check_prerequisites() {
  if [ -z "${AWS_ACCESS_KEY_ID}" ]; then
    echo "Please configure AWS_ACCESS_KEY_ID env variable. Exiting 1..."
    exit 1
  fi
  if [ -z "${AWS_SECRET_ACCESS_KEY}" ]; then
    echo "Please configure AWS_SECRET_ACCESS_KEY env variable. Exiting 1..."
    exit 1
  fi
  if [ -z "${AWS_SECURITY_GROUP}" ]; then
    echo "Please configure AWS_SECURITY_GROUP env variable. Exiting 1..."
    exit 1
  fi
  if [ -z "${AWS_SUBNET}" ]; then
    echo "Please configure AWS_SUBNET env variable. Exiting 1..."
    exit 1
  fi
  if ! command -v ansible &> /dev/null; then
    echo "ansible command could not be found. Exiting 1..."
    exit 1
  fi
  if ! command -v terraform &> /dev/null; then
    echo "terraform command could not be found. Exiting 1..."
    exit 1
  fi
}

setup_environment_and_run_tests() {
  export GITHUB_RUN_ID=$RANDOM
  envsubst < main.tf.tmpl > main.tf
  terraform init
  terraform apply -auto-approve
  echo "Removing old tgz package"
  rm splunk-connect-for-snmp.tgz
  cd ../../..
  echo "Creating tgz of the SC4SNMP repository"
  tar -czf splunk-connect-for-snmp.tgz splunk-connect-for-snmp
  echo "Moving tgz to the final directory"
  mv splunk-connect-for-snmp.tgz splunk-connect-for-snmp/integration_tests/scripts
  cd splunk-connect-for-snmp/integration_tests/scripts
  echo "Running ansible playbook"
  ansible-playbook -v playbook.yml || echo "Test run was unsuccessful"
}

destroy_environment() {
  terraform destroy -auto-approve
}

source ./set_env.sh
check_prerequisites
setup_environment_and_run_tests
#destroy_environment
