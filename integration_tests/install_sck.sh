sudo microk8s helm3 repo add splunk-otel-collector-chart https://signalfx.github.io/splunk-otel-collector-chart
sudo microk8s helm3 upgrade --install sck \
  --set="clusterName=my-cluster" \
  --set="splunkPlatform.endpoint=https://$(hostname -I | cut -d " " -f1):8088/services/collector" \
  --set="splunkPlatform.insecureSkipVerify=true" \
  --set="splunkPlatform.token=$(cat hec_token)" \
  --set="splunkPlatform.metricsEnabled=true" \
  --set="splunkPlatform.metricsIndex=em_metrics" \
  --set="splunkPlatform.index=em_logs" \
  splunk-otel-collector-chart/splunk-otel-collector
