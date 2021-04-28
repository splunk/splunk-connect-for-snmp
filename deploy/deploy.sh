#!/bin/bash

echo "      [.. ..      [..                 [.. ..  [...     [..[..       [..[.......   "
echo "    [..    [.. [..   [..      [..   [..    [..[. [..   [..[. [..   [...[..    [.. "
echo "     [..      [..           [ [..    [..      [.. [..  [..[.. [.. [ [..[..    [.. "
echo "       [..    [..          [. [..      [..    [..  [.. [..[..  [..  [..[.......   "
echo "          [.. [..        [..  [..         [.. [..   [. [..[..   [.  [..[..        "
echo "    [..    [.. [..   [..[.... [. [..[..    [..[..    [. ..[..       [..[..        "
echo "      [.. ..     [....        [..     [.. ..  [..      [..[..       [..[..        "


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

if [ "$USER" != "root" ];
then
    echo "must be root try sudo"
    exit
fi

K8S=${K8S:-mk8s}  
if [ "$K8S" = "mk8s" ]; then
  if ! command -v snap &> /dev/null
  then
      echo "snap could not be found"
      exit
  fi
  if ! command -v microk8s &> /dev/null
  then
      snap install microk8s --classic
      microk8s status --wait-ready
  fi
  if command -v microk8s.helm3 &> /dev/null
    then
    microk8s enable helm3    
  fi
  module_dns=$(sudo microk8s status -a dns)
  if [ "$module_dns" = "disabled" ];
  then
    while [ ! -n "$RESOLVERIP" ]
    do
      mresolverip=$(cat /etc/resolv.conf | grep '^nameserver ' | cut -d ' ' -f 2 | grep -v '^127\.' | head -n 1)
      mresolverip=${mresolverip:-8.8.8.8}
      read -p "RESOLVERIP IP of internal DNS resolver default ${mresolverip}: " RESOLVERIP  
      RESOLVERIP=${RESOLVERIP:=$mresolverip}
      microk8s enable dns:$RESOLVERIP
    done
  fi
fi

module_mlb=$(sudo microk8s status -a metallb)
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
    microk8s enable metallb:$SHAREDIP
  done
fi

HCMD=helm
if ! command -v helm &> /dev/null
then
    if command -v microk8s.helm3 &> /dev/null
    then
        HCMD=microk8s.helm3
    else
        echo "helm3 could not be found"
        exit
    fi
fi

KCMD=kubectl
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

# CUSTER_NAME=${CUSTER_NAME:=splunk-connect}
# NAMESPACE=${NAMESPACE:=default}

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
            echo "MODE invalid"
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
    read -p 'PORT of Splunk HEC Inputs 443 (default): ' PROTO  
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
    read -p 'EVENTS_INDEX for splunk em_events (default): ' EVENTS_INDEX  
    EVENTS_INDEX=${EVENTS_INDEX:-em_events}  
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
    read -p 'METRICS_INDEX for splunk (default): ' METRICS_INDEX  
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
    read -p 'META_INDEX for splunk default: ' META_INDEX  
    META_INDEX=${META_INDEX:-em_logs}  
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

  $HCMD repo add splunk https://splunk.github.io/splunk-connect-for-kubernetes/  >/dev/null 
  $HCMD uninstall -n sck sck
  cat deploy/sck/sck_145.yaml \
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
      | $HCMD -n sck install sck -f - splunk/splunk-connect-for-kubernetes
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

$KCMD delete ns sc4snmp --wait=true 2>/dev/null
$KCMD create ns sc4snmp 2>/dev/null  || true

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



$KCMD -n sc4snmp create -f deploy/sc4snmp/ftr 2>/dev/null

while [ ! -n "$SHAREDIP" ]
do
  read -p 'SHAREDIP for HA installations this is in addition to the member addresses for single instance this is the host ip: ' SHAREDIP  
  
done
svcip=$(echo $SHAREDIP | cut -d '/' -f 1)
cat deploy/sc4snmp/external/traps-service.yaml \
      | sed "s/##SHAREDIP##/${svcip}/g" \
      | $KCMD -n sc4snmp apply -f -

$KCMD -n sc4snmp apply -f deploy/sc4snmp/internal

echo ""
echo done
