#!/bin/bash
#!/bin/bash

DIR="rendered"
prefix="$DIR/values_"
suffix=".yaml"
declare -a TEST_CASES=()

for file in $prefix*; do
  if [ -f "$file" ]; then
    filename=${file#"$prefix"}     # Remove prefix.
    filename=${filename%"$suffix"} # Remove suffix.
    TEST_CASES+=("$filename")      # Append to array.
  fi
done

for test_case in "${TEST_CASES[@]}"; do
  VALUES_FILE="$DIR/values_${test_case}.yaml"
  MANIFEST_DIR="$DIR/manifests/tests_${test_case}"
  helm template --values "${VALUES_FILE}" --output-dir "${MANIFEST_DIR}" -n default charts/splunk-connect-for-snmp
  rm -rf "${MANIFEST_DIR}"/splunk-connect-for-snmp/charts
done
