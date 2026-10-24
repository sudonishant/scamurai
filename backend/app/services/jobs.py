"""Bounded job execution.

The smallest runnable milestone uses an in-process ThreadPoolExecutor with
durability in the relational store. When SCAMURAI_REDIS_URL is set the same task
contracts move to Celery (see worker.py); job *state* always lives in the
database, so broker persistence is never mistaken for exactly-once delivery.

Lifecycle (queued|running|waiting_for_access|waiting_for_review|completed|
failed|cancelled) is separate from outcome (complete|partial|
insufficient_evidence): a run can finish its bounded work and still have
partial coverage.

Concurrency note: each task receives ONE session and reaches checkpoints to
commit, so worker threads never self-deadlock on database write locks.
"""
from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import SessionLocal
from ..models import Job, JobEvent, utcnow

log = logging.getLogger("scamurai.jobs")
settings = get_settings()
POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="scamurai-worker")


# --------------------------------------------------------------------- helpers
def _emit(db: Session, job: Job, event_type: str, payload: dict) -> None:
    last = db.scalar(
        select(JobEvent.seq).where(JobEvent.job_id == job.id).order_by(JobEvent.seq.desc())
    )
    db.add(JobEvent(job_id=job.id, seq=(last or 0) + 1, event_type=event_type,
                    payload=json.dumps(payload)))
    db.flush()


def emit_event(job_id: str, event_type: str, payload: dict) -> None:
    """Session-bound event helper for callers that already hold a session."""
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job:
            _emit(db, job, event_type, payload)
            db.commit()


class JobContext:
    """Passed to every task: single session, stage checkpoints, cancellation."""

    def __init__(self, job: Job, db: Session):
        self.db = db
        self.job_id = job.id
        self.case_id = job.case_id
        self.deadline = time.monotonic() + settings.run_deadline_seconds
        self.limitations: list[str] = []
        self.warnings: list[str] = []
        self.counts: dict[str, int] = {}

    def stage(self, name: str) -> None:
        job = self.db.get(Job, self.job_id)
        if job is None:
            return
        job.stage = name
        _emit(self.db, job, "stage", {"stage": name})
        self.db.flush()

    def event(self, event_type: str, payload: dict) -> None:
        job = self.db.get(Job, self.job_id)
        if job:
            _emit(self.db, job, event_type, payload)

    def bump(self, key: str, amount: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + amount

    def checkpoint(self):
        """Persist progress, then enforce cooperative cancellation/deadline."""
        self.db.commit()
        job = self.db.get(Job, self.job_id)
        if time.monotonic() > self.deadline:
            raise TimeoutError("Run deadline exceeded; stopping at checkpoint")
        if job and job.cancel_requested:
            raise CancelledError("Cancellation requested")

    def limit(self, message: str) -> None:
        self.limitations.append(message)
        self.event("limitation", {"message": message})

    def warn(self, message: str) -> None:
        self.warnings.append(message)
        self.event("warning", {"message": message})


class CancelledError(RuntimeError):
    pass


# --------------------------------------------------------------------- enqueue / run
def create_or_get_job(
    db: Session, case_id: str, kind: str, parameters: dict,
    client_idempotency_key: str | None, run_id: str | None = None,
) -> tuple[Job, bool]:
    """Returns (job, created). Duplicate keys return the existing job."""
    if client_idempotency_key:
        existing = db.scalar(
            select(Job).where(
                Job.case_id == case_id,
                Job.client_idempotency_key == client_idempotency_key,
            )
        )
        if existing:
            return existing, False
    job = Job(
        case_id=case_id, kind=kind, parameters=json.dumps(parameters),
        client_idempotency_key=client_idempotency_key, run_id=run_id,
    )
    db.add(job)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        job = db.scalar(
            select(Job).where(
                Job.case_id == case_id,
                Job.client_idempotency_key == client_idempotency_key,
            )
        )
        return job, False
    _emit(db, job, "queued", {"kind": kind})
    db.commit()
    return job, True


def submit(job_id: str, kind: str) -> None:
    """Dispatch through Celery whenever a broker is configured.

    There is deliberately no silent thread-pool fallback: a configured but
    unavailable broker is surfaced as a failed/retryable job.
    """
    if settings.redis_url:
        try:
            from worker import celery_app
            if celery_app is None:
                raise RuntimeError("Celery is configured but its worker app is unavailable")
            celery_app.send_task("scamurai.execute_job", args=[job_id, kind], queue="scamurai")
        except Exception as exc:
            with SessionLocal() as db:
                job = db.get(Job, job_id)
                if job is not None:
                    _fail(db, job_id, f"Queue dispatch failed: {exc}", True, JobContext(job, db))
            raise
        return
    POOL.submit(_run_safely, job_id, kind)


def _run_safely(job_id: str, kind: str) -> None:
    # Imported lazily so connector/CLI modules do not load every pipeline.
    from .tasks import resolve_task

    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None or job.lifecycle in {"completed", "cancelled"}:
            return
        job.lifecycle = "running"
        job.started_at = utcnow()
        job.stage = "starting"
        _emit(db, job, "started", {})
        db.commit()
        ctx = JobContext(job, db)
        try:
            result = resolve_task(job)(ctx) or {}
            job = db.get(Job, job_id)
            job.counts = json.dumps({**ctx.counts, **result.get("counts", {})})
            job.limitations = json.dumps(ctx.limitations + result.get("limitations", []))
            job.warnings = json.dumps(ctx.warnings + result.get("warnings", []))
            job.lifecycle = "completed"
            job.outcome = result.get("outcome", "complete")
            job.stage = "completed"
            job.ended_at = utcnow()
            _emit(db, job, "completed", {"outcome": job.outcome, "counts": json.loads(job.counts)})
            db.commit()
        except CancelledError:
            db.rollback()
            job = db.get(Job, job_id)
            job.lifecycle = "cancelled"
            job.ended_at = utcnow()
            job.limitations = json.dumps(ctx.limitations)
            _emit(db, job, "cancelled", {"preserved_evidence": True})
            db.commit()
        except TimeoutError as exc:
            db.rollback()
            _fail(db, job_id, str(exc), retryable=True, ctx=ctx)
        except Exception as exc:  # noqa: BLE001 — worker boundary must never die silently
            log.exception("job %s failed", job_id)
            db.rollback()
            _fail(db, job_id, str(exc), retryable=False, ctx=ctx)


def _fail(db: Session, job_id: str, message: str, retryable: bool, ctx: JobContext) -> None:
    job = db.get(Job, job_id)
    if job is None:
        return
    job.lifecycle = "failed"
    job.error = message[:1000]
    job.ended_at = utcnow()
    job.limitations = json.dumps(ctx.limitations)
    job.warnings = json.dumps(ctx.warnings + [f"retryable={retryable}"])
    if ctx.counts:
        job.outcome = "partial"  # evidence collected before failure is preserved
    _emit(db, job, "failed", {"error": message, "retryable": retryable})
    db.commit()


def request_cancel(db: Session, job: Job) -> None:
    job.cancel_requested = True
    _emit(db, job, "cancel_requested", {})
    db.commit()


def reconcile_orphans() -> None:
    """Recover only in-process jobs after an API process restart.

    Celery owns queued/running delivery with late acknowledgements; an API
    restart must not fail jobs that are still waiting for an active worker.
    """
    if settings.redis_url:
        return
    with SessionLocal() as db:
        orphans = db.scalars(select(Job).where(Job.lifecycle.in_(["running", "queued"]))).all()
        for job in orphans:
            job.lifecycle = "failed"
            job.outcome = "partial"
            job.error = "Interrupted by worker restart; rerun is idempotent"
            job.ended_at = utcnow()
        db.commit()


def read_events(db: Session, job_id: str, after_seq: int = 0) -> list[JobEvent]:
    return db.scalars(
        select(JobEvent)
        .where(JobEvent.job_id == job_id, JobEvent.seq > after_seq)
        .order_by(JobEvent.seq)
    ).all()
