#!/usr/bin/env sh
set -e
. /app/.venv/bin/activate
. /app/construct-connection-strings.sh
LOG_LEVEL=${LOG_LEVEL:=INFO}
WORKER_CONCURRENCY=${WORKER_CONCURRENCY:=4}
MAX_TASKS_PER_CHILD=${MAX_TASKS_PER_CHILD:=0}
MAX_TASKS_FLAG=""
if [ "$MAX_TASKS_PER_CHILD" -gt 0 ] 2>/dev/null; then
    MAX_TASKS_FLAG="--max-tasks-per-child=$MAX_TASKS_PER_CHILD"
fi

wait-for-dep ${REDIS_DEPENDENCIES} "${MONGO_WAIT}" "${MIB_INDEX}"

ENABLE_TRAPS_SECRETS=${ENABLE_TRAPS_SECRETS:=false}
ENABLE_WORKER_POLLER_SECRETS=${ENABLE_WORKER_POLLER_SECRETS:=false}
wait-for-dep "${REDIS_DEPENDENCIES}" "${MONGO_URI}" "${MIB_INDEX}"
if [ "$ENABLE_TRAPS_SECRETS" = "true" ] || [ "$ENABLE_WORKER_POLLER_SECRETS" = "true" ]; then
    python /app/secrets/manage_secrets.py
fi
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
        celery -A splunk_connect_for_snmp.poller worker -l "$LOG_LEVEL" -Q traps --autoscale=8,"$WORKER_CONCURRENCY" $MAX_TASKS_FLAG
        ;;
    worker-poller)
        celery -A splunk_connect_for_snmp.poller worker -l "$LOG_LEVEL"  -O fair -Q poll --autoscale=8,"$WORKER_CONCURRENCY" $MAX_TASKS_FLAG
        ;;
    worker-sender)
        celery -A splunk_connect_for_snmp.poller worker -l "$LOG_LEVEL" -Q send --autoscale=6,"$WORKER_CONCURRENCY" $MAX_TASKS_FLAG
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