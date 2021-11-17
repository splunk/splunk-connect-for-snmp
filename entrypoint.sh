#!/usr/bin/env bash
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
    python -m splunk_connect_for_snmp.traps
    ;;
*)
echo -n "unknown cmd $@"
;;
esac