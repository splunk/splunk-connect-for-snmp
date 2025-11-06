#!/usr/bin/env sh
# Constructs REDIS_URL and CELERY_BROKER_URL from components if not already set

# Detect mode
REDIS_MODE="${REDIS_MODE:-standalone}"

# Only construct if URLs not already set
if [ -z "$REDIS_URL" ] || [ -z "$CELERY_BROKER_URL" ]; then

  if [ "$REDIS_MODE" = "replication" ]; then
    # Sentinel HA mode
    echo "Redis mode: Sentinel HA"

    REDIS_SENTINEL_SERVICE="${REDIS_SENTINEL_SERVICE:-snmp-redis-sentinel}"
    REDIS_SENTINEL_PORT="${REDIS_SENTINEL_PORT:-26379}"
    REDIS_MASTER_NAME="${REDIS_MASTER_NAME:-mymaster}"
    REDIS_DB="${REDIS_DB:-1}"
    CELERY_DB="${CELERY_DB:-0}"

    if [ -n "$REDIS_PASSWORD" ]; then
      SENTINEL_SCHEME="sentinel://:${REDIS_PASSWORD}@${REDIS_SENTINEL_SERVICE}:${REDIS_SENTINEL_PORT}"
      REDBEAT_SCHEME="redis-sentinel://:${REDIS_PASSWORD}@${REDIS_SENTINEL_SERVICE}:${REDIS_SENTINEL_PORT}"
    else
      SENTINEL_SCHEME="sentinel://${REDIS_SENTINEL_SERVICE}:${REDIS_SENTINEL_PORT}"
      REDBEAT_SCHEME="redis-sentinel://${REDIS_SENTINEL_SERVICE}:${REDIS_SENTINEL_PORT}"
    fi

    # Celery broker uses sentinel://
    : "${CELERY_BROKER_URL:=${SENTINEL_SCHEME}/${CELERY_DB}}"

    # RedBeat uses redis-sentinel:// with master_name query
    : "${REDIS_URL:=${REDBEAT_SCHEME}/${REDIS_DB}?master_name=${REDIS_MASTER_NAME}}"

    # For healthcheck / wait-for-dep
    REDIS_CHECK_URL="redis://${REDIS_SENTINEL_SERVICE}:${REDIS_SENTINEL_PORT}"
    CELERY_CHECK_URL="redis://${REDIS_SENTINEL_SERVICE}:${REDIS_SENTINEL_PORT}"

  else
    # Standalone mode
    echo "Redis mode: Standalone"
    REDIS_HOST="${REDIS_HOST:-snmp-redis}"
    REDIS_PORT="${REDIS_PORT:-6379}"

    if [ -n "$REDIS_PASSWORD" ]; then
      BASE="redis://:$REDIS_PASSWORD@$REDIS_HOST:$REDIS_PORT"
    else
      BASE="redis://$REDIS_HOST:$REDIS_PORT"
    fi

    : "${REDIS_URL:=$BASE/${REDIS_DB:-1}}"
    : "${CELERY_BROKER_URL:=$BASE/${CELERY_DB:-0}}"

    REDIS_CHECK_URL="${REDIS_URL}"
    CELERY_CHECK_URL="${CELERY_BROKER_URL}"
  fi

  export REDIS_URL
  export CELERY_BROKER_URL
  export REDIS_CHECK_URL
  export CELERY_CHECK_URL
  export REDIS_MODE
  export REDIS_SENTINEL_SERVICE REDIS_SENTINEL_PORT REDIS_MASTER_NAME

  echo "REDIS_URL=${REDIS_URL}"
  echo "REDIS_CHECK_URL=${REDIS_CHECK_URL}"
  echo "CELERY_BROKER_URL=${CELERY_BROKER_URL}"
fi
