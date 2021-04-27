#!/bin/bash
INSECURE_SSL=${INSECURE_SSL:=false}
PROTO=${PROTO:=https}
PORT=${PORT:=8088}
EVENTS_INDEX=${EVENTS_INDEX:=em_events}
METRICS_INDEX=${METRICS_INDEX:=em_metrics}
META_INDEX=${META_INDEX:=em_meta}
CUSTER_NAME=${CUSTER_NAME:=splunk-connect}
NAMESPACE=${NAMESPACE:=default}

if [ ! -n "$HOST" ]; then
    echo print_error "Undefined environment variable HOST ..."
    exit 1
fi
if [ ! -n "$TOKEN" ]; then
    echo print_error "Undefined environment variable TOKEN ..."
    exit 1
fi

if ! command -v realpath &> /dev/null
then
    echo "realpath could not be found"
    exit
fi
HCMD=helm3
if ! command -v helm3 &> /dev/null
then
    if command -v microk8s.helm3 &> /dev/null
    then
        HCMD=microk8s.helm3
    else
        echo "realpath could not be found"
        exit
    fi
fi

full_path=$(realpath $0)
dir_path=$(dirname $full_path)

cat ${dir_path}/sck_145.yaml \
     | sed "s/##INSECURE_SSL##/${INSECURE_SSL}/g" \
     | sed "s/##PROTO##/${PROTO}/g" \
     | sed "s/##PORT##/${PORT}/g" \
     | sed "s/##HOST##/${HOST}/g" \
     | sed "s/##TOKEN##/${TOKEN}/g" \
     | sed "s/##EVENTS_INDEX##/${EVENTS_INDEX}/g" \
     | sed "s/##METRICS_INDEX##/${METRICS_INDEX}/g"  \
     | sed "s/##META_INDEX##/${META_INDEX}/g" \
     | sed "s/##CUSTER_NAME##/${CUSTER_NAME}/g" \
     | sed "s/##NAMESPACE##/${NAMESPACE}/g" \
     | $HCMD -n ${NAMESPACE} install sck -f - splunk/splunk-connect-for-kubernetes

