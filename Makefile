.PHONY: render
render:
	rm -rf rendered/manifests
	helm template -n default --values rendered/values.yaml --output-dir rendered/manifests/tests charts/splunk-connect-for-snmp
	rm -rf rendered/manifests/tests/splunk-connect-for-snmp/charts
	./render_manifests.sh
