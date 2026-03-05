#!/bin/bash

INSECURE_SSL=true
PROTO=https
PORT=8088
SPLUNK_HOST=$1
SPLUNK_PASSWORD=$2
TOKEN=00000000-0000-0000-0000-000000000000
EVENTS_INDEX=em_events
METRICS_INDEX=em_metrics
META_INDEX=em_meta

kapply(){
  if [ -f $2 ]; then  src_cmd="cat $2"; else src_cmd="curl -s https://raw.githubusercontent.com/splunk/splunk-connect-for-snmp/$BRANCH/$2"; fi

  $src_cmd \
    | sed -e "s/##SHAREDIP##/${svcip}/g;s/##INSECURE_SSL##/${INSECURE_SSL}/g;s/##PROTO##/${PROTO}/g;s/##PORT##/${PORT}/g;s/##HOST##/${HOST}/g;s/##TOKEN##/${TOKEN}/g;s/##EVENTS_INDEX##/${EVENTS_INDEX}/g;s/##METRICS_INDEX##/${METRICS_INDEX}/g;s/##META_INDEX##/${META_INDEX}/g;s/##CLUSTER_NAME##/${CLUSTER_NAME}/g;s/##NAMESPACE##/${NAMESPACE}/g" \
    | kubectl -n $1 apply -f -
}

create_splunk_indexes() {
  splunk_ip=$1
  splunk_password=$2
  index_names=("em_metrics" "em_meta" "em_events")
  index_types=("metric" "event" "event")
  for index in "${!index_names[@]}" ; do
    if ! curl -k -u admin:"${splunk_password}" "https://${splunk_ip}:8089/services/data/indexes" \
      -d datatype="${index_types[${index}]}" -d name="${index_names[${index}]}" ; then
      echo "Error when creating ${index_names[${index}]} of type ${index_types[${index}]}"
    fi
  done
}

update_scheduler_inventory() {
  valid_snmp_get_ip=$1
  # These extra spaces are required to fit the structure in scheduler-config.yaml
  scheduler_config=$(cat << EOF
    ${valid_snmp_get_ip}:161,2c,public,1.3.6.1.2.1.1.1.0,1
    ${valid_snmp_get_ip}:161,2c,public,1.3.6.1.2.1.25.1.1,1
EOF
)
  scheduler_config=$(echo "${scheduler_config}" | \
    cat ../deploy/sc4snmp/ftr/scheduler-inventory.yaml - | kubectl apply -n sc4snmp -f -)
  echo "${scheduler_config}"
}

kubectl create namespace flux
kapply flux ../deploy/helm-operator/namespace.yaml
kapply flux ../deploy/helm-operator/crds.yaml
kapply flux ../deploy/helm-operator/rbac.yaml
kapply flux ../deploy/helm-operator/deployment.yaml

kapply sc4snmp ../deploy/sc4snmp/namespace.yaml
kapply sc4snmp ../deploy/celery-queue.yaml
kapply sc4snmp ../deploy/mongo-cache.yaml

kubectl -n sc4snmp delete secret remote-splunk

kubectl -n sc4snmp create secret generic remote-splunk \
    --from-literal=SPLUNK_HEC_URL=$PROTO://$HOST$URI_PORT/services/collector \
    --from-literal=SPLUNK_HEC_TLS_SKIP_VERIFY=$INSECURE_SSL \
    --from-literal=SPLUNK_HEC_TOKEN=$TOKEN

kapply sc4snmp ../deploy/sc4snmp/ftr/scheduler-config.yaml
kapply sc4snmp ../deploy/sc4snmp/ftr/scheduler-inventory.yaml
kapply sc4snmp ../deploy/sc4snmp/ftr/traps-server-config.yaml
kapply sc4snmp ../deploy/sc4snmp/external/traps-service.yaml

kapply sc4snmp ../deploy/sc4snmp/internal/otel-config.yaml
kapply sc4snmp ../deploy/sc4snmp/internal/otel-deployment.yaml
kapply sc4snmp ../deploy/sc4snmp/internal/otel-service.yaml
kapply sc4snmp ../deploy/sc4snmp/internal/mib-server-deployment.yaml
kapply sc4snmp ../deploy/sc4snmp/internal/mib-server-service.yaml
kapply sc4snmp ../deploy/sc4snmp/internal/traps-deployment.yaml
kapply sc4snmp ../deploy/sc4snmp/internal/scheduler-deployment.yaml
kapply sc4snmp ../deploy/sc4snmp/internal/worker-deployment.yaml

kapply sc4snmp snmp-sim-deployment.yaml
kapply sc4snmp snmp-sim-service.yaml

kubectl config set-context --current --namespace=sc4snmp

create_splunk_indexes ${SPLUNK_HOST} ${SPLUNK_PASSWORD}

simulator_internal_ip=$(kubectl -n sc4snmp get service/snmp-sim-service | tail -1 | sed 's/  */ /g' | cut -d ' ' -f 3)

update_scheduler_inventory ${simulator_internal_ip}