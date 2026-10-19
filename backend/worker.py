"""Optional Celery worker.

The default local build uses an in-process ThreadPoolExecutor (see
services/jobs.py). When PS03_REDIS_URL is configured, this module exposes the
same task contracts on a durable Celery broker. Job state always stays in the
relational store; broker persistence is not exactly-once, so every task is
idempotent and crash-reconciliation runs on startup.

Run:  celery -A worker.celery_app worker --loglevel=INFO
"""
from __future__ import annotations

import os

from app.config import get_settings
from app.services.jobs import _run_safely

settings = get_settings()

try:
    from celery import Celery
except ImportError:  # optional dependency until Redis/Celery is deployed
    Celery = None  # type: ignore[assignment]

if Celery and settings.redis_url:
    celery_app = Celery("scamurai", broker=settings.redis_url, backend=settings.redis_url)
    celery_app.conf.update(
        task_acks_late=True,                 # redeliver if a worker dies
        task_reject_on_worker_lost=True,
        broker_transport_options={"visibility_timeout": 3600},
        task_default_retry_delay=5,
    )

    from app.services import pipeline

    for _name, _fn in pipeline.WORKFLOWS.items():
        # Closure binding per task name; each task reuses the safe runner with
        # checkpointing, cancellation and idempotent writes.
        def _make(fn):
            @celery_app.task(name=f"ps03.{fn.__name__}", bind=True, max_retries=3)
            def _task(self, job_id: str):
                _run_safely(job_id, fn)
            return _task
        globals()[f"task_{_name}"] = _make(_fn)
else:
    celery_app = None  # type: ignore[assignment]
    if not os.environ.get("PS03_SUPPRESS_WORKER_NOTICE"):
        print("[worker] Celery/Redis not configured — using in-process job runner.")
