#!/bin/sh
set -e
. /venv/bin/activate

case $1 in

celery)
    case $2 in
    beat)
        celery -A splunk_connect_for_snmp.app_poller beat  --loglevel=INFO
        ;;
    worker)
        celery -A splunk_connect_for_snmp.app_poller worker --loglevel=INFO
        ;;
    *)
        celery -A splunk_connect_for_snmp.app_poller ${@:3} --loglevel=INFO
        ;;
    esac
    ;;
trap)
    echo -n "trap"
    ;;

*)
echo -n "unknown cmd $@"
;;
esac