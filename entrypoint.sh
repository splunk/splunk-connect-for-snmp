#!/usr/bin/env bash
set -e
. /app/.venv/bin/activate
LOG_LEVEL=${LOG_LEVEL:=INFO}
WORKER_CONCURRENCY=${WORKER_CONCURRENCY:=4}
wait-for-dep "${CELERY_BROKER_URL}" "${REDIS_URL}" "${MONGO_URI}" "${MIB_INDEX}"

case $1 in

inventory)
    inventory-loader
    ;;

celery)
    case $2 in
    beat)
        celery -A splunk_connect_for_snmp.poller beat -l "$LOG_LEVEL" --max-interval=5
        ;;
    worker-trap)
        celery -A splunk_connect_for_snmp.poller worker -l "$LOG_LEVEL" -Q traps --autoscale=10,"$WORKER_CONCURRENCY"
        ;;
    worker-poller)
        celery -A splunk_connect_for_snmp.poller worker -l "$LOG_LEVEL"  -O fair -Q poll --autoscale=8,"$WORKER_CONCURRENCY"
        ;;
    worker-sender)
        celery -A splunk_connect_for_snmp.poller worker -l "$LOG_LEVEL" -Q send --autoscale=10,"$WORKER_CONCURRENCY"
        ;;
    *)
        celery "$2"
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