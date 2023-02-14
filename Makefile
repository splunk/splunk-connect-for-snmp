.PHONY: render
render:
	rm -rf rendered/manifests
	helm template -n default --values rendered/values.yaml --output-dir rendered/manifests/tests charts/splunk-connect-for-snmp
	rm -rf rendered/manifests/tests/splunk-connect-for-snmp/charts
	test_cases=("only_polling", "only_traps", "autoscaling_enabled", "autoscaling_enabled_deprecated") ; \
	for test_case in $(test_cases) ; do \
	    helm template -n default --values rendered/values_($test_case).yaml --output-dir rendered/manifests/tests_($test_case)/splunk-connect-for-snmp ; \
	    rm -rf rendered/manifests/tests_($test_case)/splunk-connect-for-snmp/charts ; \
	done
