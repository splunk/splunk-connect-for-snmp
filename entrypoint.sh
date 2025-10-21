#!/usr/bin/env sh
set -e
. /app/.venv/bin/activate
LOG_LEVEL=${LOG_LEVEL:=INFO}
WORKER_CONCURRENCY=${WORKER_CONCURRENCY:=4}

# Only construct if URLs not already set
if [ -z "$REDIS_URL" ] || [ -z "$CELERY_BROKER_URL" ]; then
  # Defaults
  REDIS_HOST="${REDIS_HOST:-snmp-redis}"
  REDIS_PORT="${REDIS_PORT:-6379}"

  # Build base
  if [ -n "$REDIS_PASSWORD" ]; then
    BASE="redis://:${REDIS_PASSWORD}@${REDIS_HOST}:${REDIS_PORT}"
  else
    BASE="redis://${REDIS_HOST}:${REDIS_PORT}"
  fi

  # Set if not already set
  : "${REDIS_URL:=$BASE/${REDIS_DB:-1}}"
  : "${CELERY_BROKER_URL:=$BASE/${CELERY_DB:-0}}"

  export REDIS_URL CELERY_BROKER_URL
fi

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