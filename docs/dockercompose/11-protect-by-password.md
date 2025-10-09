## Protect Mongo and Redis by password

In your `docker-compose.yaml` [specify](https://hub.docker.com/r/bitnami/redis) for Redis container `REDIS_PASSWORD` or `REDIS_PASSWORD_FILE`:

```
  redis:
  ...
    environment:
      - REDIS_PASSWORD=...
```

The same thing you to [specify](https://hub.docker.com/r/bitnami/mongodb) for Mongo container using `MONGODB_ROOT_PASSWORD`:

```
  mongo:
  ...
    environment:
      - MONGODB_ROOT_PASSWORD=...
```

After that just update connection string:

```
REDIS_URL: redis://:pass@redis:6379/1
CELERY_BROKER_URL: redis://:pass@redis:6379/0
MONGO_URI: mongodb://root:pass@mongo:27017/
```

!!! Warning
    If you wanna update the password you need to make it manually using `mongo` and `redis` cli.
    And only after that you need to update `REDIS_PASSWORD`/ `MONGODB_ROOT_PASSWORD` and connection strings.
