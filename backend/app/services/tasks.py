"""Shared job resolver for in-process and Celery execution.

Task names, rather than Python callables, cross the broker boundary. Both
runners therefore resolve the same persisted Job kind and parameters.
"""
from __future__ import annotations

import json
from collections.abc import Callable

from ..models import Comment, Job
from . import comments as comments_svc
from . import pipeline


def _transform_task(spec_name: str, entity_id: str) -> Callable:
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
                raise ValueError("Comment not found in this case")
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


def resolve_task(job: Job) -> Callable:
    kind = job.kind
    workflow = kind.removeprefix("agent:")
    if workflow in pipeline.WORKFLOWS:
        return pipeline.WORKFLOWS[workflow]
    if kind.startswith("transform:"):
        parameters = json.loads(job.parameters or "{}")
        return _transform_task(kind.split(":", 1)[1], str(parameters.get("entity") or ""))
    raise ValueError(f"No registered task for job kind: {kind}")
