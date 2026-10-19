"""Controlled agent endpoint (master prompt section 16).

The agent never executes anything itself: each validated tool call is mapped
to either an existing bounded workflow job or an honest 'provider disabled'
abstention. Policy validation happens server-side for every step.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import JobOut
from ..security import get_current_user, require_case
from ..services.agent import BoundedAgent, ToolCall, ToolResult
from ..services.jobs import create_or_get_job, submit
from ..services import pipeline

router = APIRouter(prefix="/api/v1/cases/{case_id}", tags=["agent"])

# Tool -> existing bounded workflow, or None when an external provider is required.
TOOL_TO_WORKFLOW = {
    "compare_images": "image_matching",
    "compute_coordination_features": "coordination_detection",
    "extract_claims": "claim_workflow",
}


class AgentRunRequest(BaseModel):
    goal: str = Field(min_length=2, max_length=120)
    step_budget: int = Field(default=8, ge=1, le=20)
    client_idempotency_key: str = Field(min_length=8, max_length=200)


class AgentRunResponse(BaseModel):
    stop_reason: str
    steps: list[dict]
    evidence_ids: list[str]
    jobs: list[JobOut]


@router.post("/agent/run", response_model=AgentRunResponse, status_code=202)
def run_agent(body: AgentRunRequest,
              ctx=Depends(require_case({"analyst", "owner"})),
              db: Session = Depends(get_db),
              _user: User = Depends(get_current_user)):
    agent = BoundedAgent(ctx.case.id, step_budget=body.step_budget)
    enqueued: list = []

    def executor(call: ToolCall) -> ToolResult:
        workflow = TOOL_TO_WORKFLOW.get(call.tool)
        if workflow is None:
            return ToolResult(
                ok=False, output={},
                limitation=("External provider is not configured for "
                            f"{call.tool}; no evidence is fabricated."))
        job, created = create_or_get_job(
            db, ctx.case.id, kind=f"agent:{workflow}",
            parameters={"via": "bounded_agent", "tool": call.tool},
            client_idempotency_key=f"{body.client_idempotency_key}:{workflow}")
        if created:
            submit(job.id, pipeline.WORKFLOWS[workflow])
        enqueued.append(job)
        return ToolResult(ok=True, output={"job_id": job.id, "workflow": workflow})

    result = agent.run(body.goal, executor)
    return AgentRunResponse(
        stop_reason=result["stop_reason"],
        steps=[{"seq": s.seq, "tool": s.tool, "ok": s.ok, "stop_reason": s.stop_reason,
                "limitation": s.limitation, "evidence_ids": s.evidence_ids} for s in result["steps"]],
        evidence_ids=result["evidence_ids"],
        jobs=[JobOut(
            id=j.id, run_id=j.run_id, kind=j.kind, lifecycle=j.lifecycle, outcome=j.outcome,
            stage=j.stage, counts=json.loads(j.counts),
            limitations=json.loads(j.limitations),
            warnings=json.loads(j.warnings), error=j.error,
            cancel_requested=j.cancel_requested, created_at=j.created_at,
            started_at=j.started_at, ended_at=j.ended_at) for j in enqueued])
