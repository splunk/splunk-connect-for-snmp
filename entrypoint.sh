#!/usr/bin/env bash
set -e
. /app/.venv/bin/activate
LOG_LEVEL=${LOG_LEVEL:=INFO}
WORKER_CONCURRENCY=${WORKER_CONCURRENCY:=2}
wait-for-dep "${CELERY_BROKER_URL}" "${MONGO_URI}" "${MIB_INDEX}"

case $1 in


celery)
    case $2 in
    beat)
        celery -A splunk_connect_for_snmp.poller beat -l "$LOG_LEVEL"
        ;;
    worker)
        celery -A splunk_connect_for_snmp.poller worker -l "$LOG_LEVEL" --concurrency="$WORKER_CONCURRENCY" -O fair
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