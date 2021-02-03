#!/bin/bash
wget https://github.com/splunk/splunk-connect-for-kubernetes/releases/download/1.3.0/splunk-connect-for-kubernetes-1.3.0.tgz -O splunk-connect-for-kubernetes.tgz 

GLOBAL_HEC_INSECURE_SSL=${GLOBAL_HEC_INSECURE_SSL:=false}
OBJECTS_INSECURE_SSL=${OBJECTS_INSECURE_SSL:=false}
METRICS_INSECURE_SSL=${METRICS_INSECURE_SSL:=false}

JOURNALD_PATH=${JOURNALD_PATH:=/run/log/journal}
KUBELET_PROTOCOL=${KUBELET_PROTOCOL:=https}
METRICS_INDEX=${METRICS_INDEX:=em_metrics}
LOG_INDEX=${LOG_INDEX:=em_logs}
META_INDEX=${META_INDEX:=em_meta}
SCK_DOWNLOAD_ONLY=${SCK_DOWNLOAD_ONLY:=false}
HELM_RELEASE_NAME=${HELM_RELEASE_NAME:=sck}
CORE_OBJ=${CORE_OBJ:=pods,nodes,component_statuses,config_maps,namespaces,persistent_volumes,persistent_volume_claims,resource_quotas,services,service_accounts,events}
APPS_OBJ=${APPS_OBJ:=daemon_sets,deployments,replica_sets,stateful_sets}


print_info() {
    echo -e "\033[32m\n $* \n\033[0m"
}

print_error() {
    echo -e "\033[31m\n $* \n\033[0m"
}

sed_inplace() {
    if [ "$(uname -s)" = "Darwin" ]; then
        sed -i '' "$1" "$2"
    else
        sed -i "$1" "$2"
    fi
}

sed_script_inplace() {
    if [ "$(uname -s)" = "Darwin" ]; then
        sed -i '' -e "$1" "$2"
    else
        sed -i -e "$1" "$2"
    fi
}

streamEditYaml() {
    # insert entity_types into configMap.yaml for metrics
    sed_script_inplace '/\/source/a\
    \    <filter kube.node.**>\
    \      @type record_modifier\
    \      <record>\
    \        entity_type k8s_node\
    \      </record>\
    \    </filter>\
    \    <filter kube.pod.**>\
    \      @type record_modifier\
    \      <record>\
    \        entity_type k8s_pod\
    \      </record>\
    \    </filter>'$'\n' "$1"

    # Use splunk-kubernetes-objects 1.1.2
    sed_inplace 's/splunk\/kube-objects:1.1.0/splunk\/kube-objects:1.1.2/' "$2"
}

metrics_configmap_yaml='splunk-connect-for-kubernetes/charts/splunk-kubernetes-metrics/templates/configMap.yaml'
objects_values_yaml='splunk-connect-for-kubernetes/charts/splunk-kubernetes-objects/values.yaml'
objects_deployment_yaml='splunk-connect-for-kubernetes/charts/splunk-kubernetes-objects/templates/deployment.yaml'


# rename yaml file
if [ -f "kubernetes_connect_template.yaml" ]; then
    # rename yaml file
    cp -f kubernetes_connect_template.yaml kubernetes_connect.yaml
else
    echo "kubernetes_connect_template.yaml was not downloaded. Exiting..."
    exit 1
fi

# update template with user defined values
if [ -n "$MONITORING_MACHINE" ]; then
    sed_inplace "s/\${monitoring_machine}/$MONITORING_MACHINE/" kubernetes_connect.yaml
else
    print_error "Undefined environment variable MONITORING_MACHINE ..."
    exit 1
fi

if [ -n "$HEC_TOKEN" ]; then
    sed_inplace "s/\${hec_token}/$HEC_TOKEN/" kubernetes_connect.yaml
else
    print_error "Undefined environment variable HEC_TOKEN ..."
    exit 1
fi

if [ -n "$HEC_PORT" ]; then
    sed_inplace "s/\${hec_port}/$HEC_PORT/" kubernetes_connect.yaml
else
    print_error "Undefined environment variable HEC_PORT ..."
    exit 1
fi

if [ -n "$METRICS_INDEX" ]; then
    sed_inplace "s/\${metrics_index}/$METRICS_INDEX/" kubernetes_connect.yaml
else
    print_error "Undefined environment variable METRICS_INDEX ..."
    exit 1
fi

if [ -n "$LOG_INDEX" ]; then
    sed_inplace "s/\${log_index}/$LOG_INDEX/" kubernetes_connect.yaml
else
    print_error "Undefined environment variable LOG_INDEX ..."
    exit 1
fi

if [ -n "$META_INDEX" ]; then
    sed_inplace "s/\${meta_index}/$META_INDEX/" kubernetes_connect.yaml
else
    print_error "Undefined environment variable META_INDEX ..."
    exit 1
fi

if [ -n "$CLUSTER_NAME" ]; then
    sed_inplace "s/\${cluster_name}/$CLUSTER_NAME/" kubernetes_connect.yaml
else
    print_error "Undefined environment variable CLUSTER_NAME ..."
    exit 1
fi

if [ -n "$KUBELET_PROTOCOL" ]; then
    if [ "${KUBELET_PROTOCOL}" = "http" ]; then
        sed_inplace "s/\${kubelet_port}/10255/" kubernetes_connect.yaml
        sed_inplace "s/\${use_https}/false/" kubernetes_connect.yaml
    elif [ "${KUBELET_PROTOCOL}" = "https" ]; then
        sed_inplace "s/\${kubelet_port}/10250/" kubernetes_connect.yaml
        sed_inplace "s/\${use_https}/true/" kubernetes_connect.yaml
    else
        print_error "Incorrect kubelet port value ..."
        exit 1
    fi
else
    print_error "Undefined environment variable KUBELET_PROTOCOL ..."
    exit 1
fi

if [ -n "$GLOBAL_HEC_INSECURE_SSL" ]; then
    sed_inplace "s/\${global_hec_insecure_ssl}/${GLOBAL_HEC_INSECURE_SSL}/" kubernetes_connect.yaml
else
    print_error "Undefined environment variable GLOBAL_HEC_INSECURE_SSL ..."
    exit 1
fi

if [ -n "$METRICS_INSECURE_SSL" ]; then
    sed_inplace "s/\${metrics_insecure_ssl}/${METRICS_INSECURE_SSL}/" kubernetes_connect.yaml
else
    print_error "Undefined environment variable METRICS_INSECURE_SSL ..."
    exit 1
fi

if [ -n "$OBJECTS_INSECURE_SSL" ]; then
    sed_inplace "s/\${objects_insecure_ssl}/${OBJECTS_INSECURE_SSL}/" kubernetes_connect.yaml
else
    print_error "Undefined environment variable OBJECTS_INSECURE_SSL ..."
    exit 1
fi

if [ -n "$JOURNALD_PATH" ]; then
    sed_inplace "s#\${journal_log_path}#${JOURNALD_PATH}#" kubernetes_connect.yaml
else
    print_error "Undefined environment variable JOURNALD_PATH ..."
    exit 1
fi

# set the core kubernetes objects
if [ -n "$CORE_OBJ" ]; then
    kube_core_objects=$CORE_OBJ
    IFS=','
    map_in_lists=""
    for each in $kube_core_objects
    do
        if [ "$each" == "events" ]; then
            map_in_lists+="{\"name\":\"$each\", \"mode\":\"watch\"}"
        else
            map_in_lists+="{\"name\":\"$each\", \"interval\":\"60s\"}"
        fi
        map_in_lists+=","
    done
    sed_inplace "s/\${kubernetes_core_objects}/[$map_in_lists]/"  kubernetes_connect.yaml
fi

# set the apps kubernetes objects
if [ -n "$APPS_OBJ" ]; then
    kube_apps_objects=$APPS_OBJ
    IFS=','
    map_in_lists=""
    for each in $kube_apps_objects
    do
        map_in_lists+="{\"name\":\"$each\", \"interval\":\"60s\"},"
    done
    sed_inplace 's/${kubernetes_apps_objects_clause}/apps:\
      v1:\
        ${kubernetes_apps_objects}/' kubernetes_connect.yaml
    sed_inplace "s/\${kubernetes_apps_objects}/[$map_in_lists]/" kubernetes_connect.yaml
else
    sed_inplace 's/ *${kubernetes_apps_objects_clause}//' kubernetes_connect.yaml
fi

create_k8_namespace() {
    microk8s kubectl create namespace "${KUBERNETES_NAMESPACE}"
    microk8s kubectl label namespace "${KUBERNETES_NAMESPACE}" name="${KUBERNETES_NAMESPACE}"
}

if [ "${SCK_DOWNLOAD_ONLY}" != "true" ]; then
    # untar splunk-connect for kubernetes
    tar -xzf splunk-connect-for-kubernetes.tgz
    streamEditYaml "./$metrics_configmap_yaml" "./$objects_values_yaml"
    # Do helm install
    create_k8_namespace
    microk8s helm3 install "${HELM_RELEASE_NAME}" ./splunk-connect-for-kubernetes --namespace="${KUBERNETES_NAMESPACE}" -f kubernetes_connect.yaml
else
    # We just want to create the manifests and render charts locally
    # create directory for charts
    mkdir -p rendered-charts
    # render templates using helm
    microk8s helm3 template "${HELM_RELEASE_NAME}" splunk-connect-for-kubernetes.tgz --namespace="${KUBERNETES_NAMESPACE}" --values kubernetes_connect.yaml --output-dir ./rendered-charts
    streamEditYaml "./rendered-charts/$metrics_configmap_yaml" "./rendered-charts/$objects_deployment_yaml"
fi