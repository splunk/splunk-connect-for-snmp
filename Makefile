.PHONY: render
render:
	helm template -n default --output-dir rendered/manifests/tests charts/splunk-connect-for-snmp
	rm -rf rendered/manifests/tests/splunk-connect-for-snmp/charts
