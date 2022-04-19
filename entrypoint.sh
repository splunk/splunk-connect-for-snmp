#!/usr/bin/env bash
set -e
. /app/.venv/bin/activate
LOG_LEVEL=${LOG_LEVEL:=INFO}
WORKER_CONCURRENCY=${WORKER_CONCURRENCY:=4}
wait-for-dep "${CELERY_BROKER_URL}" "${MONGO_URI}" "${MIB_INDEX}"

case $1 in

inventory)
    inventory-loader
    ;;

celery)
    case $2 in
    beat)
        celery -A splunk_connect_for_snmp.poller beat -l "$LOG_LEVEL"
        ;;
    worker-trap)
        celery -A splunk_connect_for_snmp.poller worker -l "$LOG_LEVEL" --concurrency="$WORKER_CONCURRENCY" -O fair -Q traps
        ;;
    worker-poller)
        celery -A splunk_connect_for_snmp.poller worker -l "$LOG_LEVEL" --concurrency="$WORKER_CONCURRENCY" -O fair -Q poll
        ;;
    worker-sender)
        celery -A splunk_connect_for_snmp.poller worker -l "$LOG_LEVEL" --concurrency="$WORKER_CONCURRENCY" -O fair -Q send
        ;;
    *)
        celery -A splunk_connect_for_snmp.poller "${@:3}" -l "$LOG_LEVEL"
        ;;
    esac
    ;;
trap)
    traps "$LOG_LEVEL"
    ;;
*)
echo -n unknown cmd "$@"
;;
esac