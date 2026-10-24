"""Runs, jobs, SSE progress, cancellation and Transforms (sections 5-6, 16-17)."""
from __future__ import annotations

import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import SessionLocal, get_db
from ..models import Comment, Input, Job
from ..policies import clamp_run_limits
from ..registry import TRANSFORMS
from ..schemas import JobOut, RunCreate, TransformCreate
from ..security import require_case
from ..services import comments as comments_svc
from ..services import pipeline
from ..services.jobs import (
    create_or_get_job, read_events, request_cancel, submit,
)

router = APIRouter(prefix="/api/v1/cases/{case_id}", tags=["runs"])

TERMINAL = {"completed", "failed", "cancelled"}


def _serialize_job(job: Job) -> JobOut:
    return JobOut(
        id=job.id, run_id=job.run_id, kind=job.kind, lifecycle=job.lifecycle,
        outcome=job.outcome, stage=job.stage, counts=json.loads(job.counts),
        limitations=json.loads(job.limitations), warnings=json.loads(job.warnings),
        error=job.error, cancel_requested=job.cancel_requested,
        created_at=job.created_at, started_at=job.started_at, ended_at=job.ended_at,
        retryable=bool(job.error and "deadline" in job.error),
    )


@router.post("/runs", status_code=202)
def create_run(body: RunCreate, ctx=Depends(require_case({"analyst", "owner"})),
               db: Session = Depends(get_db)):
    if body.workflow not in pipeline.WORKFLOWS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown workflow")
    case_limits = json.loads(ctx.case.limits)
    effective_limits = clamp_run_limits(case_limits, body.limits, get_settings())
    if len(set(body.input_ids)) != len(body.input_ids):
        raise HTTPException(422,
                            "Run input IDs must be unique")
    owned_inputs = []
    if body.input_ids:
        owned_inputs = db.scalars(select(Input).where(
            Input.case_id == ctx.case.id, Input.id.in_(body.input_ids))).all()
        if {item.id for item in owned_inputs} != set(body.input_ids):
            raise HTTPException(422,
                                "Run input IDs must belong to this case")
    url_seed_count = sum(item.kind == "url" for item in owned_inputs)
    if url_seed_count > effective_limits["max_seed_urls"]:
        raise HTTPException(422,
                            "Seed URL count exceeds case policy limit")
    run_id = str(uuid.uuid4())
    job, created = create_or_get_job(
        db, ctx.case.id, kind=body.workflow,
        parameters={"input_ids": body.input_ids, "limits": effective_limits,
                    "allowed_provider_ids": body.allowed_provider_ids},
        client_idempotency_key=body.client_idempotency_key, run_id=run_id)
    if created:
        submit(job.id, pipeline.WORKFLOWS[body.workflow])
    return {"run_id": job.run_id, "job_id": job.id, "replayed": not created}


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, ctx=Depends(require_case()), db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None or job.case_id != ctx.case.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return _serialize_job(job)


@router.get("/jobs")
def list_jobs(ctx=Depends(require_case()), db: Session = Depends(get_db)):
    jobs = db.scalars(select(Job).where(Job.case_id == ctx.case.id)
                      .order_by(Job.created_at.desc()).limit(50)).all()
    return [_serialize_job(j) for j in jobs]


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, ctx=Depends(require_case({"analyst", "owner"})),
               db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None or job.case_id != ctx.case.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    if job.lifecycle not in TERMINAL:
        request_cancel(db, job)
    return {"job_id": job.id, "cancel_requested": True,
            "note": "New work stops at the next checkpoint; collected evidence is preserved."}


@router.get("/events")
async def stream_events(ctx=Depends(require_case()),
                        last_event_id: str | None = Header(default=None),
                        db: Session = Depends(get_db)):
    after_seq = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0

    async def generator():
        seq = after_seq
        idle = 0
        while True:
            with SessionLocal() as session:
                latest_job = session.scalar(
                    select(Job).where(Job.case_id == ctx.case.id)
                    .order_by(Job.created_at.desc()))
                if latest_job is None:
                    yield ": waiting for first job\n\n"
                    await asyncio.sleep(0.5)
                    continue
                events = read_events(session, latest_job.id, seq)
                for event in events:
                    seq = event.seq
                    payload = json.dumps({"seq": event.seq, "event_type": event.event_type,
                                          "payload": json.loads(event.payload),
                                          "created_at": event.created_at.isoformat()})
                    yield f"id: {event.seq}\nevent: {event.event_type}\ndata: {payload}\n\n"
                terminal = latest_job.lifecycle in TERMINAL and not events
            if terminal:
                idle += 1
                if idle >= 2:  # flush tail then close
                    break
            await asyncio.sleep(0.5)

    return StreamingResponse(generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# --------------------------------------------------------------------- transforms
def _transform_task(spec_name: str, entity_type: str, entity_id: str, parameters: dict):
    def task(job_ctx):
        db = job_ctx.db
        if spec_name in ("extract_ocr", "reverse_image_search"):
            return {"outcome": "insufficient_evidence",
                    "limitations": [f"{spec_name} is disabled: no approved provider configured. "
                                    "Mocks are never presented as real evidence."]}
        if spec_name in ("import_comments", "import_authorized_posts"):
            return {"outcome": "insufficient_evidence",
                    "limitations": ["Use authorized CSV/JSON upload for this account/post; "
                                    "no live platform connector is configured."]}
        if spec_name == "analyze_comment":
            comment = db.get(Comment, entity_id)
            if comment is None or comment.case_id != job_ctx.case_id:
                raise HTTPException(404, "Comment not in case")
            record = comments_svc.analyze_and_store(db, job_ctx.case_id, entity_id)
            return {"counts": {"categories": len(json.loads(record.categories))},
                    "outcome": "complete"}
        if spec_name in ("find_exact_duplicates", "find_visual_variants"):
            return pipeline.image_matching(job_ctx)
        if spec_name == "compute_coordination_features":
            return pipeline.coordination_detection(job_ctx)
        if spec_name in ("extract_claims", "plan_claim_searches"):
            return pipeline.claim_workflow(job_ctx)
        if spec_name == "estimate_capture_location":
            return pipeline.location_analysis(job_ctx)
        return {"outcome": "insufficient_evidence",
                "limitations": [f"Transform {spec_name} has no local implementation"]}
    return task


@router.post("/transforms", status_code=202)
def run_transform(body: TransformCreate,
                  ctx=Depends(require_case({"analyst", "owner"})),
                  db: Session = Depends(get_db)):
    spec = TRANSFORMS.get(body.transform)
    if spec is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown transform")
    if body.entity_type not in spec.applies_to:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"Transform {body.transform} cannot run on {body.entity_type}")
    job, created = create_or_get_job(
        db, ctx.case.id, kind=f"transform:{body.transform}",
        parameters={"entity": body.entity_id, "parameters": body.parameters},
        client_idempotency_key=body.client_idempotency_key)
    if created:
        submit(job.id, _transform_task(body.transform, body.entity_type,
                                       body.entity_id, body.parameters))
    return {"job_id": job.id, "transform": body.transform,
            "provider_warning": "external provider required" if spec.needs_external else "local",
            "replayed": not created}
