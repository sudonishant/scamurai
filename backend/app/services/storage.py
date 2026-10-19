"""Private object storage.

Local disk in development; the same interface maps to an S3-compatible bucket
when PS03_S3_ENDPOINT is configured (boto3 is an optional dependency).
Metadata and object keys live in PostgreSQL/SQLite — never the bytes themselves.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from ..config import get_settings

settings = get_settings()


def _root() -> Path:
    root = Path(settings.storage_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def put_object(case_id: str, key: str, data: bytes) -> str:
    path = _root() / case_id / key
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write-temp-then-renove: crash-safe, no partial snapshots.
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
    return f"{case_id}/{key}"


def get_object(object_key: str) -> bytes:
    return (_root() / object_key).read_bytes()


def object_path(object_key: str) -> Path:
    return _root() / object_key


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
