"""Celery worker for durable, database-tracked Scamurai jobs.

Run: celery -A worker.celery_app worker --loglevel=INFO --queues=scamurai

Late acknowledgement protects against worker loss, not exactly-once execution.
Tasks therefore use idempotent writes and the API never treats broker state as
the investigation lifecycle. A visibility timeout longer than the run deadline
avoids concurrent redelivery of a healthy long-running task.
"""
from __future__ import annotations

import os

from app.config import get_settings
from app.services.jobs import _run_safely

settings = get_settings()

try:
    from celery import Celery
except ImportError:  # local-only installations may omit the worker extra
    Celery = None  # type: ignore[assignment]

if Celery and settings.redis_url:
    celery_app = Celery("scamurai", broker=settings.redis_url, backend=settings.redis_url)
    celery_app.conf.update(
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        broker_connection_retry_on_startup=True,
        broker_transport_options={"visibility_timeout": max(
            3600, settings.run_deadline_seconds * 2)},
        result_expires=24 * 3600,
        task_default_queue="scamurai",
        task_routes={"scamurai.execute_job": {"queue": "scamurai"}},
        task_soft_time_limit=settings.run_deadline_seconds,
        task_time_limit=settings.run_deadline_seconds + 30,
        task_default_retry_delay=5,
    )

    @celery_app.task(name="scamurai.execute_job", bind=True, max_retries=3)
    def execute_job_task(self, job_id: str, kind: str):
        # Application failures are persisted on Job and are not hidden by
        # infinite broker retries. Infrastructure redelivery is handled by
        # Celery's late-ack/worker-loss policy above.
        _run_safely(job_id, kind)

else:
    celery_app = None  # type: ignore[assignment]
    if not os.environ.get("SCAMURAI_SUPPRESS_WORKER_NOTICE"):
        print("[worker] Celery/Redis not configured — using in-process job runner.")
