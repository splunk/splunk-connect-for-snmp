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
  terraform apply -auto-approve
  ansible-playbook -v playbook.yml || echo "Test run was unsuccessful"
}

desstroy_environment() {
  setup_environment_and_run_tests
}

source ./set_env.sh
check_prerequisites
setup_environment_and_run_tests
desstroy_environment
