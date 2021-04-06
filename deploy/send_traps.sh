#!/bin/bash
# kubectl get all | grep -i trap


### Installation via yum / apt ###
# sudo yum install net-snmp-utils -y
#
# apt update
# apt install snmpd snmp libsnmp-dev
###


send_traps() {

CLUSTER_IP=$1
CLUSTER_PORT=$2
EXT_IP=$3
EXT_PORT=$4

snmptrap -v 2c -c public $CLUSTER_IP:$CLUSTER_PORT 123 1.3.6.1.6.3.1.1.5.1 1.3.6.1.2.1.1.5.0 s test1
snmptrap -v 2c -c public $CLUSTER_IP:$EXT_PORT 123 1.3.6.1.6.3.1.1.5.1 1.3.6.1.2.1.1.5.0 s test2
snmptrap -v 2c -c public $EXT_IP:$EXT_PORT 123 1.3.6.1.6.3.1.1.5.1 1.3.6.1.2.1.1.5.0 s test3
snmptrap -v 2c -c public $EXT_IP:$CLUSTER_PORT 123 1.3.6.1.6.3.1.1.5.1 1.3.6.1.2.1.1.5.0 s test4
}


send_traps  172.31.23.29 162 10.43.219.119 32130