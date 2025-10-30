#!/usr/bin/env sh
set -e
. /app/.venv/bin/activate
. /app/construct-redis-url.sh
LOG_LEVEL=${LOG_LEVEL:=INFO}
WORKER_CONCURRENCY=${WORKER_CONCURRENCY:=4}

# Use REDIS_CHECK_URL for dependency waiting in Sentinel mode
REDIS_WAIT_URL="${REDIS_CHECK_URL:-$REDIS_URL}"

wait-for-dep "${CELERY_BROKER_URL}" "${REDIS_WAIT_URL}" "${MONGO_URI}" "${MIB_INDEX}"

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
        celery -A splunk_connect_for_snmp.poller worker -l "$LOG_LEVEL" -Q traps --autoscale=8,"$WORKER_CONCURRENCY"
        ;;
    worker-poller)
        celery -A splunk_connect_for_snmp.poller worker -l "$LOG_LEVEL"  -O fair -Q poll --autoscale=8,"$WORKER_CONCURRENCY"
        ;;
    worker-sender)
        celery -A splunk_connect_for_snmp.poller worker -l "$LOG_LEVEL" -Q send --autoscale=6,"$WORKER_CONCURRENCY"
        ;;
    flower)
        celery -A splunk_connect_for_snmp.poller flower
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