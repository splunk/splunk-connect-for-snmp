"""Fixtures for SC4SNMP integration tests using an explicitly selected local Redis."""

import os
import shutil
import subprocess
import time
from uuid import uuid4

import pytest
from celery import Celery
from redbeat.schedulers import RedBeatSchedulerEntry
from redis import Redis
from redis.exceptions import ConnectionError


@pytest.fixture
def app(tmp_path, monkeypatch):
    """
    Start a private Redis process for application scheduling checks.

    No shared Redis, MongoDB, SNMP device or output endpoint is contacted.
    The process has only a Unix socket and is removed after the test.

    :param tmp_path: Temporary directory for this test's Redis socket
    :param monkeypatch: Fixture restoring the constructor isolation

    :return: Celery app using private Redis storage and a memory broker
    """
    # Constructor mocks in other tests can change Python's allocation slot.
    monkeypatch.setattr(
        RedBeatSchedulerEntry,
        "__new__",
        staticmethod(lambda cls, *args, **kwargs: object.__new__(cls)),
    )
    executable = os.environ.get("REDBEAT_TEST_REDIS_SERVER")
    if not executable:
        pytest.skip("Set REDBEAT_TEST_REDIS_SERVER to an isolated Redis test binary")
    executable = shutil.which(executable)
    if not executable:
        pytest.fail("The requested Redis test binary is unavailable")
    socket_path = str(tmp_path / "redis.sock")
    process = subprocess.Popen(
        [
            executable,
            "--port",
            "0",
            "--unixsocket",
            socket_path,
            "--unixsocketperm",
            "700",
            "--save",
            "",
            "--appendonly",
            "no",
            "--dir",
            str(tmp_path),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    client = Redis(unix_socket_path=socket_path, decode_responses=True)
    result = None
    try:
        deadline = time.monotonic() + 5
        while True:
            if process.poll() is not None:
                pytest.fail("Isolated Redis exited before startup")
            try:
                client.ping()
                break
            except ConnectionError:
                if time.monotonic() >= deadline:
                    pytest.fail("Isolated Redis did not become ready")
                time.sleep(0.02)
        result = Celery("real-jitter-tests", broker="memory://", set_as_current=False)
        result.conf.update(
            redbeat_redis_url="redis://unused/0",
            timezone="UTC",
            task_default_queue="jitter-" + uuid4().hex,
        )
        result.redbeat_redis = client
        yield result
    finally:
        if result is not None:
            result.close()
        client.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
