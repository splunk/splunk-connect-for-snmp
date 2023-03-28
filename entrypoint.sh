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
        celery -A splunk_connect_for_snmp.poller beat -l "$LOG_LEVEL" --max-interval=10
        ;;
    worker-trap)
        celery -A splunk_connect_for_snmp.poller worker -l "$LOG_LEVEL" -O fair -Q traps -c "$WORKER_CONCURRENCY" --without-heartbeat --without-gossip --without-mingle
        ;;
    worker-poller)
        celery -A splunk_connect_for_snmp.poller worker -l "$LOG_LEVEL"  -O fair -Q poll -c "$WORKER_CONCURRENCY" --without-heartbeat --without-gossip --without-mingle
        ;;
    worker-sender)
        celery -A splunk_connect_for_snmp.poller worker -l "$LOG_LEVEL" -O fair -Q send -c "$WORKER_CONCURRENCY" --without-heartbeat --without-gossip --without-mingle
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