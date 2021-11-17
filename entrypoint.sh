#!/usr/bin/env bash
set -e
echo args "$@"
. /app/.venv/bin/activate
LOG_LEVEL=${LOG_LEVEL:=INFO}

wait-for-dep "${CELERY_BROKER_URL}"
wait-for-dep "${MONGO_URI}"

case $1 in


celery)
    case $2 in
    beat)
        celery -A splunk_connect_for_snmp.poller beat  --loglevel=$LOG_LEVEL
        ;;
    worker)
        celery -A splunk_connect_for_snmp.poller worker --loglevel=$LOG_LEVEL
        ;;
    *)
        celery -A splunk_connect_for_snmp.poller "${@:3}" --loglevel=$LOG_LEVEL
        ;;
    esac
    ;;
trap)
    python -m splunk_connect_for_snmp.traps --loglevel=$LOG_LEVEL
    ;;
*)
echo -n unknown cmd "$@"
;;
esac