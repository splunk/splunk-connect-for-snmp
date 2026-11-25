import json
import os
from pathlib import Path


def read_private_json(path):
    path = Path(path).resolve(strict=True)
    if path.stat().st_mode & 0o077:
        raise ValueError("Runtime JSON files must be readable only by their owner")
    return json.loads(path.read_text())


def write_private(path, content):
    path = Path(path)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(content)


def write_container_file(path, content):
    write_private(path, content)
    if os.geteuid() == 0:
        os.chown(path, 10001, 10001)
    elif os.geteuid() != 10001:
        Path(path).chmod(0o640)
