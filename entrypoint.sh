#!/usr/bin/env sh
set -e
. /app/.venv/bin/activate
LOG_LEVEL=${LOG_LEVEL:=INFO}
WORKER_CONCURRENCY=${WORKER_CONCURRENCY:=4}

# Detect Redis mode
REDIS_MODE="${REDIS_MODE:-standalone}"

# Only construct if URLs not already set
if [ -z "$REDIS_URL" ] || [ -z "$CELERY_BROKER_URL" ]; then

  if [ "$REDIS_MODE" = "sentinel" ]; then
    # Sentinel HA mode
    echo "Redis mode: Sentinel HA"
    REDIS_SENTINEL_SERVICE="${REDIS_SENTINEL_SERVICE:-snmp-redis-sentinel}"
    REDIS_SENTINEL_PORT="${REDIS_SENTINEL_PORT:-26379}"
    REDIS_MASTER_NAME="${REDIS_MASTER_NAME:-mymaster}"
    REDIS_DB="${REDIS_DB:-1}"
    CELERY_DB="${CELERY_DB:-0}"

    # Build Sentinel URL
    if [ -n "$REDIS_PASSWORD" ]; then
      SENTINEL_BASE="sentinel://:%s@${REDIS_SENTINEL_SERVICE}:${REDIS_SENTINEL_PORT}"
    else
      SENTINEL_BASE="sentinel://${REDIS_SENTINEL_SERVICE}:${REDIS_SENTINEL_PORT}"
    fi

    # Note: For wait-for-dep, we check Sentinel service itself
    REDIS_CHECK_URL="redis://${REDIS_SENTINEL_SERVICE}:${REDIS_SENTINEL_PORT}"

    # For application use (Python will handle Sentinel discovery)
    : "${REDIS_URL:=${SENTINEL_BASE}/${REDIS_DB}}"
    : "${CELERY_BROKER_URL:=${SENTINEL_BASE}/${CELERY_DB}}"

  else
    # Standalone mode (existing logic)
    echo "Redis mode: Standalone"
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

    REDIS_CHECK_URL="${REDIS_URL}"
  fi

  export REDIS_URL CELERY_BROKER_URL
  export REDIS_MODE REDIS_SENTINEL_SERVICE REDIS_SENTINEL_PORT REDIS_MASTER_NAME
fi

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