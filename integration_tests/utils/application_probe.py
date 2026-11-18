import ast
import json
import logging
import os
import socket
import sys
import threading
import time


def main():
    logging.disable(logging.CRITICAL)
    request = json.load(sys.stdin)
    from celery import Celery
    from redbeat.decoder import RedBeatJSONDecoder
    from redbeat.schedulers import ensure_conf, get_redis

    app = Celery("jitter-integration-observer", set_as_current=False)
    app.config_from_object("splunk_connect_for_snmp.celery_config")
    conf = ensure_conf(app)
    connection = get_redis(app)
    devices = {
        f"{device['address']}:{device['port']}": device["label"]
        for device in request["devices"]
    }
    action = request.get("action", "snapshot")
    if action in ("events", "observe"):
        # A stop line also works when Kubernetes does not forward stdin EOF.
        def stop_on_disconnect():
            sys.stdin.readline()
            os._exit(0)

        threading.Thread(target=stop_on_disconnect, daemon=True).start()
    if action == "events":
        capture_events(app, devices, request["duration"])
        result = {"capture_complete": True}
    elif action == "observe":
        capture_snapshots(connection, conf, devices, request["duration"])
        result = {"capture_complete": True}
    elif action == "configure_mongo":
        from pymongo import MongoClient

        from splunk_connect_for_snmp.common.common import human_bool

        allowed = {device["address"] for device in request["devices"]}
        allowed.update(request["config"]["groups"])
        if any(row["address"] not in allowed for row in request["rows"]):
            raise RuntimeError("Mongo inventory contains a non-fixture target")
        with MongoClient(os.environ["MONGO_URI"]) as mongo:
            database = mongo[os.getenv("MONGO_DB", "sc4snmp")]
            previous = database.used_ui.find_one({}) or {}
            if previous.get("used_ui"):
                records = [
                    {
                        **row,
                        "port": int(row.get("port") or 161),
                        "walk_interval": int(row["walk_interval"]),
                        "delete": human_bool(row.get("delete"), False),
                        "smart_profiles": human_bool(row.get("smart_profiles"), False),
                    }
                    for row in request["rows"]
                ]
                # These are the native UI source collections in the isolated DB.
                # The normal inventory Job still owns reconciliation and schedules.
                for name, documents in (
                    ("inventory_ui", records),
                    (
                        "profiles_ui",
                        [
                            {key: value}
                            for key, value in request["config"]["profiles"].items()
                        ],
                    ),
                    (
                        "groups_ui",
                        [
                            {key: value}
                            for key, value in request["config"]["groups"].items()
                        ],
                    ),
                ):
                    collection = database[name]
                    collection.delete_many({})
                    if documents:
                        collection.insert_many(documents)
        result = {"updated": bool(previous.get("used_ui"))}
    elif action == "failover_redis":
        from redis.backoff import NoBackoff
        from redis.exceptions import (
            AuthenticationError,
            AuthorizationError,
            ConnectionError,
            TimeoutError,
        )
        from redis.retry import Retry
        from redis.sentinel import SentinelConnectionPool

        pool = connection.connection_pool
        if not isinstance(pool, SentinelConnectionPool):
            raise RuntimeError("The selected Redis connection does not use Sentinel")
        previous_primary = connection.info("server")["run_id"]
        manager = pool.sentinel_manager
        manager.sentinels[0].sentinel_failover(pool.service_name)
        options = dict(pool.connection_kwargs)
        options.pop("connection_pool", None)
        options.update(
            socket_timeout=1,
            socket_connect_timeout=1,
            retry=Retry(NoBackoff(), 0),
        )
        deadline = time.monotonic() + request.get("timeout", 60)
        while time.monotonic() < deadline:
            try:
                with manager.master_for(
                    pool.service_name,
                    **options,
                ) as primary:
                    changed = primary.info("server")["run_id"] != previous_primary
                    healthy = primary.info("replication")["role"] == "master"
                    if changed and healthy:
                        break
            except (AuthenticationError, AuthorizationError):
                raise
            except (ConnectionError, TimeoutError):
                pass
            time.sleep(0.5)
        else:
            raise RuntimeError("A different healthy Redis primary was not confirmed")
        result = {
            "requested": True,
            "changed_primary": True,
            "completed_at": time.time(),
        }
    elif action == "step_down_mongo":
        from pymongo import MongoClient
        from pymongo.errors import AutoReconnect

        with MongoClient(
            os.environ["MONGO_URI"],
            serverSelectionTimeoutMS=1000,
            connectTimeoutMS=1000,
            socketTimeoutMS=1000,
        ) as mongo:
            previous = mongo.admin.command("hello")
            if not previous.get("setName"):
                raise RuntimeError(
                    "The selected MongoDB deployment is not a replica set"
                )
            try:
                mongo.admin.command("replSetStepDown", 10, force=True)
            except AutoReconnect:
                pass
            deadline = time.monotonic() + request.get("timeout", 60)
            while time.monotonic() < deadline:
                try:
                    current = mongo.admin.command("hello")
                    if (
                        current.get("isWritablePrimary")
                        and current.get("primary") != previous["primary"]
                    ):
                        break
                except AutoReconnect:
                    pass
                time.sleep(0.5)
            else:
                raise RuntimeError(
                    "A different healthy MongoDB primary was not confirmed"
                )
        result = {
            "requested": True,
            "changed_primary": True,
            "completed_at": time.time(),
        }
    elif action in ("drained", "state"):
        replies = app.control.inspect(timeout=3, limit=request["expected_workers"])
        active = replies.active() or {}
        reserved = replies.reserved() or {}
        scheduled = replies.scheduled() or {}
        workers = set(active)
        complete = len(workers) == request["expected_workers"] and workers == set(
            reserved
        ) == set(scheduled)
        with app.connection_for_read() as broker:
            channel = broker.channel()
            client = channel.client
            queue_keys = {
                channel._q_for_pri(queue.name, priority)
                for queue in app.conf.task_queues
                for priority in channel.priority_steps
            }
            queued = sum(client.llen(key) for key in queue_keys)
            unacked = client.hlen(channel.unacked_key)
            unacked_index = client.zcard(channel.unacked_index_key)
        result = {
            "drained": complete
            and not any(active.values())
            and not any(reserved.values())
            and not any(scheduled.values())
            and queued == unacked == unacked_index == 0,
            "queued": queued,
            "unacked": unacked,
            "unacked_index": unacked_index,
            "workers": len(workers),
            "worker_replies_complete": complete,
        }
        if action == "state":
            result.update(read_snapshot(connection, conf, devices))
    elif action == "remove_schedules":
        # This explicit state-loss case removes only the fixture's hashes.
        # Normal inventory/WALK processing must reconstruct them afterward.
        selected = set(request["selected"])
        removed = 0
        keys = connection.zrange(conf.schedule_key, 0, -1)
        for key in keys:
            raw = connection.hget(key, "definition")
            if raw is None:
                continue
            definition = json.loads(raw, cls=RedBeatJSONDecoder)
            target = definition.get("kwargs", {}).get("address")
            if target not in devices:
                continue
            interval = int(definition["schedule"].run_every.total_seconds())
            kind = definition["task"].rsplit(".", 1)[-1]
            if f"{devices[target]}/{kind}/{interval}" in selected:
                removed += connection.delete(key)
        result = {"removed": removed}
    else:
        result = read_snapshot(connection, conf, devices)
    print("JITTER_RESULT=" + json.dumps(result), flush=True)
    connection.close()
    app.close()


def read_snapshot(connection, conf, devices):
    from redbeat.decoder import RedBeatJSONDecoder

    observed_at = time.time()
    entries = {}
    foreign_entries = 0
    for key in connection.zrange(conf.schedule_key, 0, -1):
        with connection.pipeline(transaction=True) as pipe:
            pipe.hget(key, "definition")
            pipe.hget(key, "meta")
            pipe.hget(key, "jitter_fingerprint")
            pipe.hget(key, "entry_id")
            pipe.zscore(conf.schedule_key, key)
            raw, raw_meta, fingerprint, entry_id, score = pipe.execute()
        if raw is None:
            continue
        definition = json.loads(raw, cls=RedBeatJSONDecoder)
        if definition["task"] == "celery.backend_cleanup":
            continue
        target = definition.get("kwargs", {}).get("address")
        if target not in devices:
            foreign_entries += 1
            continue
        meta = json.loads(raw_meta or "{}", cls=RedBeatJSONDecoder)
        interval = definition["schedule"].run_every.total_seconds()
        if interval.is_integer():
            interval = int(interval)
        last_run = meta.get("last_run_at")
        kind = definition["task"].rsplit(".", 1)[-1]
        label = devices[target]
        entries[f"{label}/{kind}/{int(interval)}"] = {
            "label": label,
            "kind": kind,
            "interval": interval,
            "due": last_run.timestamp() + interval if last_run else None,
            "last_run_at": last_run.timestamp() if last_run else None,
            "count": meta.get("total_run_count", 0),
            "score": score,
            "fingerprint": json.loads(fingerprint or "null"),
            "entry_id": json.loads(entry_id or "null"),
            "immediate": str(definition.get("run_immediately", False)).lower()
            in ("true", "1"),
            "first_run_kwargs": definition.get("first_run_kwargs", {}),
            "profiles": definition.get("kwargs", {}).get("profiles", []),
            "walk_profile": definition.get("kwargs", {}).get("profile"),
            "group": definition.get("kwargs", {}).get("group"),
        }
    result = {
        "observed_at": observed_at,
        "finished_at": time.time(),
        "entries": entries,
        "foreign_entries": foreign_entries,
    }
    return result


def capture_snapshots(connection, conf, devices, duration):
    from redis.exceptions import RedisError

    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        started = time.monotonic()
        try:
            snapshot = read_snapshot(connection, conf, devices)
        except RedisError as error:
            print(
                "JITTER_SNAPSHOT_GAP="
                + json.dumps(
                    {"observed_at": time.time(), "error": type(error).__name__}
                ),
                flush=True,
            )
        else:
            print(
                "JITTER_SNAPSHOT=" + json.dumps(snapshot),
                flush=True,
            )
        time.sleep(max(0, 0.05 - (time.monotonic() - started)))


def capture_events(app, devices, duration):
    received = {}

    def record(event):
        uuid = event.get("uuid")
        if event.get("type") == "task-received":
            kwargs = event.get("kwargs", {})
            if isinstance(kwargs, str):
                try:
                    kwargs = ast.literal_eval(kwargs)
                except (ValueError, SyntaxError):
                    return
            if not isinstance(kwargs, dict):
                return
            label = devices.get(kwargs.get("address"))
            kind = event.get("name", "").rsplit(".", 1)[-1]
            if label is not None and kind in ("walk", "poll"):
                frequency = kwargs.get("frequency")
                received[uuid] = {
                    "label": label,
                    "kind": kind,
                    "frequency": (
                        frequency if isinstance(frequency, (int, float)) else None
                    ),
                }
        if uuid in received:
            result = dict(
                received[uuid],
                uuid=uuid,
                state=event["type"],
                timestamp=event["timestamp"],
            )
            print("JITTER_EVENT=" + json.dumps(result), flush=True)

    deadline = time.monotonic() + duration
    with app.connection_for_read() as broker:
        receiver = app.events.Receiver(broker, handlers={"*": record})
        with receiver.consumer_context() as (connection, _, _):
            app.control.enable_events()
            next_enable = time.monotonic() + 5
            print("JITTER_EVENT_READY", flush=True)
            while time.monotonic() < deadline:
                if time.monotonic() >= next_enable:
                    # New workers can announce themselves before accepting
                    # control commands. Keep task events enabled after rollouts.
                    app.control.enable_events()
                    next_enable = time.monotonic() + 5
                try:
                    connection.drain_events(
                        timeout=min(1, max(0, deadline - time.monotonic()))
                    )
                except socket.timeout:
                    connection.heartbeat_check()


if __name__ == "__main__":
    main()
