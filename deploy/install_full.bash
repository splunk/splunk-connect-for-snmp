#!/bin/bash

echo "      [.. ..      [..                 [.. ..  [...     [..[..       [..[.......    "
echo "    [..    [.. [..   [..      [..   [..    [..[. [..   [..[. [..   [...[..    [..  "
echo "     [..      [..           [ [..    [..      [.. [..  [..[.. [.. [ [..[..    [..  "
echo "       [..    [..          [. [..      [..    [..  [.. [..[..  [..  [..[.......    "
echo "          [.. [..        [..  [..         [.. [..   [. [..[..   [.  [..[..         "
echo "    [..    [.. [..   [..[.... [. [..[..    [..[..    [. ..[..       [..[..         "
echo "      [.. ..     [....        [..     [.. ..  [..      [..[..       [..[..         "


realpath() {
  OURPWD=$PWD
  cd "$(dirname "$1")"
  LINK=$(readlink "$(basename "$1")")
  while [ "$LINK" ]; do
    cd "$(dirname "$LINK")"
    LINK=$(readlink "$(basename "$1")")
  done
  REALPATH="$PWD/$(basename "$1")"
  cd "$OURPWD"
  echo "$REALPATH"
}

kapply(){
  if [ -f $2 ]; then  src_cmd="cat $2"; else src_cmd="curl -s https://raw.githubusercontent.com/splunk/splunk-connect-for-snmp/$BRANCH/$2"; fi
    
  $src_cmd \
    | sed -e "s/##SHAREDIP##/${svcip}/g;s/##INSECURE_SSL##/${INSECURE_SSL}/g;s/##PROTO##/${PROTO}/g;s/##PORT##/${PORT}/g;s/##HOST##/${HOST}/g;s/##TOKEN##/${TOKEN}/g;s/##EVENTS_INDEX##/${EVENTS_INDEX}/g;s/##METRICS_INDEX##/${METRICS_INDEX}/g;s/##META_INDEX##/${META_INDEX}/g;s/##CLUSTER_NAME##/${CLUSTER_NAME}/g;s/##NAMESPACE##/${NAMESPACE}/g" \
    | $KCMD -n $1 apply -f -
}

verify_dependencies() {
    echo "[-] Check Squashfs status! 📦 "
    echo "\t (squashfs is the dependency for snap package)"
    echo .
    echo .

    echo "[-] Checking whether Squashfs is enabled or not..."
    module_squashfs_disabled=$(sudo grep -nri "squashfs" /etc/modprobe.d/ | grep -v "#" | wc -l)
    if [ "$module_squashfs_disabled" -gt 0 ]; then
        echo .
        echo "⚠️ Caution: SquashFS is disabled. See below:"
        echo .
        echo "----"    
        sudo grep -nri "squashfs" /etc/modprobe.d/  | grep -v "#"
        echo "----" 
        echo .
        echo "ℹ️Easy fix: you may remove or comment the line containing 'install squashfs /bin/true' to re-activate the squashfs."
        echo "ℹ️Reboot the host after following above steps."
    else
        echo "✅ SquashFS is enabled."
    fi
}


install_dependencies_on_centos7() {
  yum -y install epel-release
  yum -y install snapd
  systemctl enable snapd
  systemctl start snapd
  sleep 10
  ln -s /var/lib/snapd/snap /snap
  yum -y install bind-utils
}

install_dependencies_on_centos8() {
  dnf -y install epel-release
  dnf -y install snapd
  systemctl enable snapd
  systemctl start snapd
  sleep 10
  ln -s /var/lib/snapd/snap /snap
  yum -y install bind-utils
}

install_dependencies() {
  os_release=/etc/os-release
  if [ ! -f "$os_release" ] ; then
    echo "$os_release does not exist"
    exit 4
  fi

  os_id=$(grep "^ID=" "$os_release" | sed -e "s/\"//g" | cut -d= -f2)
  if [ "$os_id" == "ubuntu" ] ; then
    echo 'Snap and nslookup install not required'
  elif [ "$os_id" == "centos" ] && grep "^VERSION_ID=\"7" $os_release>/dev/null; then
    install_dependencies_on_centos7
  elif [ "$os_id" == "centos" ] && grep "^VERSION_ID=\"8" $os_release>/dev/null; then
    install_dependencies_centos8
  elif [ "$os_id" == "rhel" ] && grep "^VERSION_ID=\"7" $os_release>/dev/null; then
    install_dependencies_on_centos7
  elif [ "$os_id" == "rhel" ] && grep "^VERSION_ID=\"8" $os_release>/dev/null; then
    install_dependencies_on_centos8
  else
    echo "Unsupported operating system: $os_id $os_version"
    exit 4
  fi  
}


###MAIN 


if [ "$USER" != "root" ];
then
    echo "must be root try sudo"
    exit
fi


KCMD=kubectl
BRANCH=${BRANCH:-main}
K8S=${K8S:-mk8s}  
if [ "$K8S" = "mk8s" ]; then

  verify_dependencies
    
  if ! command -v snap &> /dev/null
  then
      install_dependencies
  fi

  if ! command -v microk8s &> /dev/null
  then
      while ! snap install microk8s --classic  &> /dev/null; do
          echo error installing mk8s using snap
          sleep 1
      done
      if [ -f ~/.bashrc ] ; then
        source ~/.bashrc
      fi
  fi
  microk8s status --wait-ready
  
  module_dns=$(microk8s status -a dns)
  if [ "$module_dns" = "disabled" ];
  then
    while [ ! -n "$RESOLVERIP" ]
    do
      mresolverip=$(cat /etc/resolv.conf | grep '^nameserver ' | cut -d ' ' -f 2 | grep -v '^127\.' | head -n 1)
      mresolverip=${mresolverip:-8.8.8.8}
      read -p "RESOLVERIP IP of internal DNS resolver default ${mresolverip}: " RESOLVERIP  
      RESOLVERIP=${RESOLVERIP:=$mresolverip}      
    done
    microk8s enable dns:$RESOLVERIP
  fi

  module_mlb=$(microk8s status -a metallb)
  if [ "$module_mlb" = "disabled" ];
  then
    while [ ! -n "$SHAREDIP" ]
    do
      msharedip=$(hostname -I | cut -d ' ' -f 1)
      echo 'SHAREDIP for HA installations use a CIDR format for a single address /32'
      echo ' * For a HA installation this should be a unassigned IP shared by the instances'
      echo ' * For a NON HA installation this should be the machine ip'
      read -p "default value for this machine is ${msharedip}/32" SHAREDIP  

      SHAREDIP=${SHAREDIP:=$msharedip/32}      
    done
    microk8s enable metallb:$SHAREDIP
  fi


  module_storage=$(microk8s status -a storage)
  if [ "$module_storage" = "disabled" ];
  then
    microk8s enable storage
  fi

  if ! command -v kubectl &> /dev/null
  then
      if command -v microk8s.kubectl &> /dev/null
      then
          KCMD=microk8s.kubectl
      else
          echo "kubectl could not be found"
          exit
      fi
  fi

fi

while [ ! -n "$SHAREDIP" ]
do
  read -p 'SHAREDIP for HA installations this is in addition to the member addresses for single instance this is the host ip: ' SHAREDIP    
done
svcip=$(echo $SHAREDIP | cut -d '/' -f 1)


#Apply the helm operator
if [ ! -n "$NOSCK" ]; then
  $KCMD create namespace flux
  kapply flux deploy/helm-operator/namespace.yaml
  kapply flux deploy/helm-operator/crds.yaml
  kapply flux deploy/helm-operator/rbac.yaml
  kapply flux deploy/helm-operator/deployment.yaml
fi

if [ ! -n "$MODE" ]; then
    read -p 'Select MODE one of splunk,sim,both: ' MODE
    case "${MODE}" in
    splunk)
            echo "MODE Splunk"
            ;;
    sim)
            echo "MODE SIM"
            ;;
    both)
            echo "MODE Both"
            ;;
    *)
            echo "MODE invalid =$MODE"
            exit 1
            ;;
    esac
fi

if [ "$MODE" == "splunk" ] || [ "$MODE" == "both" ];
then

  while [ ! -n "$HOST" ]
  do
    read -p 'FQDN of Splunk HEC Inputs: ' HOST

    resolvedIP=$(nslookup "$HOST" | awk -F':' '/^Address: / { matched = 1 } matched { print $2}' | xargs)
    if [[ -z "$resolvedIP" ]]; then
      echo "$HOST" lookup failure
      unset HOST 
    fi
  done

  while [ ! -n "$PROTO" ]
  do
    read -p 'PROTO of Splunk HEC Inputs http or https (default): ' PROTO  
    PROTO=${PROTO:-https}
  done

  while [ ! -n "$PORT" ]
  do
    read -p 'PORT of Splunk HEC Inputs 443 (default): ' PORT  
    PORT=${PORT:-443}  
  done
  URI_PORT=":$PORT"

  if [ "$PROTO" = "https" ]; then
    while [ ! -n "$INSECURE_SSL" ]
    do
      read -p 'INSECURE_SSL allow true or false (default): ' INSECURE_SSL  
      INSECURE_SSL=${INSECURE_SSL:-false}  
      if [ "$INSECURE_SSL" == "true" ] || [ "$INSECURE_SSL" == "false" ];
      then
        echo ""
      else
        unset INSECURE_SSL
      fi
    done 
  fi

  if [ "$INSECURE_SSL" == "true" ];
  then
    CURL_SSL=-k
  fi

  while [ ! -n "$TOKEN" ]
  do
    read -p 'TOKEN of Splunk HEC Inputs: ' TOKEN   
  done

  echo testing HEC url
  curl -f $CURL_SSL $PROTO://$HOST$URI_PORT/services/collector -H "Authorization: Splunk $TOKEN" -d '{"event": "test" }'
  if [ "$?" != "0" ]; 
  then
    echo Splunk URL test failed
    exit 1
  fi
  echo ""
  while [ ! -n "$EVENTS_INDEX" ]
  do
    echo ""
    read -p 'EVENTS_INDEX for splunk em_logs (default): ' EVENTS_INDEX  
    EVENTS_INDEX=${EVENTS_INDEX:-em_logs}  
    echo testing HEC url with index $EVENTS_INDEX
    curl -f $CURL_SSL $PROTO://$HOST$URI_PORT/services/collector -H "Authorization: Splunk $TOKEN" -d "{\"index\": \"$EVENTS_INDEX\", \"event\": \"test\" }"
    if [ "$?" != "0" ]; 
    then
      unset EVENTS_INDEX
    fi
  done

  while [ ! -n "$METRICS_INDEX" ]
  do
    echo ""
    read -p 'METRICS_INDEX for splunk em_metrics (default): ' METRICS_INDEX  
    METRICS_INDEX=${METRICS_INDEX:-em_metrics}  
    echo testing HEC url with index $METRICS_INDEX
    curl -f $CURL_SSL $PROTO://$HOST$URI_PORT/services/collector -H "Authorization: Splunk $TOKEN" -d "{\"index\": \"$METRICS_INDEX\", \"event\": \"metric\" }"
    if [ "$?" != "0" ]; 
    then
      unset METRICS_INDEX
    fi
  done

  while [ ! -n "$META_INDEX" ]
  do
    echo ""
    read -p 'META_INDEX for splunk em_meta (default): ' META_INDEX  
    META_INDEX=${META_INDEX:-em_meta}  
    echo testing HEC url with index $META_INDEX
    curl -f $CURL_SSL $PROTO://$HOST$URI_PORT/services/collector -H "Authorization: Splunk $TOKEN" -d "{\"index\": \"$META_INDEX\", \"event\": \"test\" }"
    if [ "$?" != "0" ]; 
    then
      unset META_INDEX
    fi
  done

  while [ ! -n "$CLUSTER_NAME" ]
  do
    read -p "CLUSTER_NAME of deployment $(hostname) (default): " CLUSTER_NAME  
    CLUSTER_NAME=${CLUSTER_NAME:=$(hostname)}
  done

  $KCMD create ns sck 2>/dev/null  || true
  kapply sck deploy/sc4snmp/sck.yaml
  
fi #end splunk or both

if [ "$MODE" == "sim" ] || [ "$MODE" == "both" ];
then
  while [ ! -n "$SIMREALM" ]
  do
    read -p 'SIMREALM Splunk SIM Realm: ' SIMREALM  
  done

  while [ ! -n "$SIMTOKEN" ]
  do
    read -p 'SIMTOKEN Splunk SIM Token: ' SIMTOKEN  
  done

fi #end sim or both

#Create the namespace
kapply sc4snmp deploy/sc4snmp/namespace.yaml

kapply sc4snmp deploy/celery-queue.yaml
kapply sc4snmp deploy/mongo-cache.yaml

#$KCMD -n sc4snmp wait --for=condition=released --timeout 180s helmrelease/celery
#$KCMD -n sc4snmp wait --for=condition=released --timeout 180s helmrelease/cache

$KCMD -n sc4snmp delete secret remote-splunk

if [ "$MODE" == "both" ];
then
  $KCMD -n sc4snmp create secret generic remote-splunk \
    --from-literal=SPLUNK_HEC_URL=$PROTO://$HOST$URI_PORT/services/collector \
    --from-literal=SPLUNK_HEC_TLS_SKIP_VERIFY=$INSECURE_SSL \
    --from-literal=SPLUNK_HEC_TOKEN=$TOKEN \
    --from-literal=SIGNALFX_TOKEN=$SIMTOKEN \
    --from-literal=SIGNALFX_REALM=$SIMREALM
fi
if [ "$MODE" == "splunk" ];
then
  $KCMD -n sc4snmp create secret generic remote-splunk \
    --from-literal=SPLUNK_HEC_URL=$PROTO://$HOST$URI_PORT/services/collector \
    --from-literal=SPLUNK_HEC_TLS_SKIP_VERIFY=$INSECURE_SSL \
    --from-literal=SPLUNK_HEC_TOKEN=$TOKEN 
fi
if [ "$MODE" == "sim" ];
then
  $KCMD -n sc4snmp create secret generic remote-splunk \
    --from-literal=SIGNALFX_TOKEN=$SIMTOKEN \
    --from-literal=SIGNALFX_REALM=$SIMREALM
fi

kapply sc4snmp deploy/sc4snmp/ftr/scheduler-config.yaml
kapply sc4snmp deploy/sc4snmp/ftr/scheduler-inventory.yaml
kapply sc4snmp deploy/sc4snmp/ftr/traps-server-config.yaml
kapply sc4snmp deploy/sc4snmp/external/traps-service.yaml

kapply sc4snmp deploy/sc4snmp/internal/otel-config.yaml
kapply sc4snmp deploy/sc4snmp/internal/otel-deployment.yaml
kapply sc4snmp deploy/sc4snmp/internal/otel-service.yaml
kapply sc4snmp deploy/sc4snmp/internal/mib-server-deployment.yaml
kapply sc4snmp deploy/sc4snmp/internal/mib-server-service.yaml
kapply sc4snmp deploy/sc4snmp/internal/traps-deployment.yaml
kapply sc4snmp deploy/sc4snmp/internal/scheduler-deployment.yaml
kapply sc4snmp deploy/sc4snmp/internal/worker-deployment.yaml

echo ""
echo done
