#!/bin/bash

TEST_CASES=("only_polling" "only_traps" "autoscaling_enabled" "autoscaling_enabled_deprecated")
for test_case in "${TEST_CASES[@]}"
  do
      VALUES_FILE=rendered/values_"${test_case}".yaml
      MANIFEST_DIR=rendered/manifests/tests_"${test_case}"
      helm template --values "${VALUES_FILE}" --output-dir "${MANIFEST_DIR}" -n default charts/splunk-connect-for-snmp
      rm -rf "${MANIFEST_DIR}"/splunk-connect-for-snmp/charts
  done