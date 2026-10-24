"""Private object storage with one byte-oriented contract.

Local disk is for development. ``STORAGE_BACKEND=s3`` uses AWS S3 or an
S3-compatible service such as MinIO; a custom ``S3_ENDPOINT`` is optional.
Metadata and object keys live in the relational database, never object bytes.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
from functools import lru_cache
from pathlib import Path, PurePosixPath

from ..config import get_settings

settings = get_settings()


def _s3_enabled() -> bool:
    # Respect the former endpoint-only configuration during migration.
    return settings.storage_backend == "s3" or bool(settings.s3_endpoint)


@lru_cache(maxsize=1)
def _s3_client():
    import boto3
    from botocore.config import Config

    if bool(settings.s3_access_key) != bool(settings.s3_secret_key):
        raise RuntimeError("Both S3_ACCESS_KEY and S3_SECRET_KEY must be set together")
    credentials = {}
    if settings.s3_access_key and settings.s3_secret_key:
        credentials = {
            "aws_access_key_id": settings.s3_access_key,
            "aws_secret_access_key": settings.s3_secret_key,
        }
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint or None,
        region_name=settings.s3_region,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path" if settings.s3_force_path_style else "auto"},
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=10,
            read_timeout=60,
        ),
        **credentials,
    )


def _key(case_id: str, key: str) -> str:
    value = str(PurePosixPath(case_id) / key.lstrip("/"))
    parts = PurePosixPath(value).parts
    if value.startswith("/") or ".." in parts or not key or "\\" in value:
        raise ValueError("Invalid object key")
    return value


def _root() -> Path:
    root = Path(settings.storage_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _local_path(object_key: str) -> Path:
    root = _root().resolve()
    path = (root / object_key).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Object key escapes the storage root")
    return path


def put_object(case_id: str, key: str, data: bytes) -> str:
    object_key = _key(case_id, key)
    if _s3_enabled():
        _s3_client().put_object(
            Bucket=settings.s3_bucket,
            Key=object_key,
            Body=data,
            ContentType="application/octet-stream",
        )
        return object_key

    path = _local_path(object_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Unique temp file + atomic replace avoids partial snapshots and writers
    # racing on the same deterministic evidence key.
    fd, temporary = tempfile.mkstemp(prefix=".scamurai-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return object_key


def get_object(object_key: str) -> bytes:
    if _s3_enabled():
        response = _s3_client().get_object(Bucket=settings.s3_bucket, Key=object_key)
        body = response["Body"]
        try:
            return body.read()
        finally:
            body.close()
    return _local_path(object_key).read_bytes()


def object_path(object_key: str) -> Path:
    """Local-only compatibility helper; new callers should stream bytes."""
    if _s3_enabled():
        raise RuntimeError("A local path is unavailable for S3 objects; use get_object()")
    return _local_path(object_key)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
