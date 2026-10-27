"""Comments corpus, per-comment analysis, findings, evidence and reviews."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    Account,
    Comment,
    CommentAnalysis,
    EvidenceRecord,
    Finding,
    MediaAsset,
    Post,
    SourceAccess,
)
from ..schemas import CommentOut, FindingOut, ReviewCreate
from ..security import require_case
from ..services import comments as comments_svc
from ..services.audit import record

router = APIRouter(prefix="/api/v1/cases/{case_id}", tags=["comments-findings"])


def _comment_out(db: Session, comment: Comment) -> CommentOut:
    analysis = db.scalar(select(CommentAnalysis).where(
        CommentAnalysis.comment_id == comment.id))
    return CommentOut(
        id=comment.id, stable_id=comment.stable_id, raw_text=comment.raw_text,
        author_ref=comment.author_ref, timestamp=comment.timestamp,
        timestamp_precision=comment.timestamp_precision,
        parent_comment_id=comment.parent_comment_id, permalink=comment.permalink,
        permalink_status=comment.permalink_status, review_status=comment.review_status,
        uncertain_duplicate=comment.uncertain_duplicate,
        analysis=({
            "categories": json.loads(analysis.categories),
            "spans": json.loads(analysis.evidence_spans),
            "explanation": analysis.explanation,
            "scores": json.loads(analysis.scores),
            "validation_status": analysis.validation_status,
            "suggested_action": analysis.suggested_action,
        } if analysis else None),
    )


@router.get("/comments", response_model=dict)
def list_comments(language: str | None = None, review_status: str | None = None,
                  q: str | None = None, offset: int = 0, limit: int = Query(50, le=200),
                  ctx=Depends(require_case()), db: Session = Depends(get_db)):
    query = select(Comment).where(Comment.case_id == ctx.case.id)
    if review_status:
        query = query.where(Comment.review_status == review_status)
    if q:
        query = query.where(Comment.raw_text.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(Comment.created_at).offset(offset).limit(limit)).all()
    access = db.scalars(select(SourceAccess).where(
        SourceAccess.case_id == ctx.case.id,
        SourceAccess.capability == "comments:read")).all()
    coverage = [json.loads(a.detail) for a in access if a.detail.startswith("{")]
    return {"total": total, "coverage": coverage,
            "items": [_comment_out(db, c) for c in rows]}


@router.post("/comments/{comment_id}/analyses", status_code=201)
def analyze_one(comment_id: str, ctx=Depends(require_case({"analyst", "owner"})),
                db: Session = Depends(get_db)):
    comment = db.get(Comment, comment_id)
    if comment is None or comment.case_id != ctx.case.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found")
    comments_svc.analyze_and_store(db, ctx.case.id, comment_id)
    record(db, ctx.user.id, "comment.analyze", "comment", comment_id, ctx.case.id)
    db.commit()
    return _comment_out(db, comment)


@router.get("/findings", response_model=list[FindingOut])
def list_findings(ctx=Depends(require_case()), db: Session = Depends(get_db)):
    rows = db.scalars(select(Finding).where(
        Finding.case_id == ctx.case.id).order_by(Finding.created_at.desc())).all()
    return [FindingOut(
        id=f.id, question=f.question, conclusion_category=f.conclusion_category,
        evidence_ids=json.loads(f.evidence_ids), excerpts=json.loads(f.excerpts),
        limitations=json.loads(f.limitations), contradictions=json.loads(f.contradictions),
        review_status=f.review_status, review_note=f.review_note,
        analysis_run_id=f.analysis_run_id, created_at=f.created_at) for f in rows]


@router.post("/findings/{finding_id}/reviews")
def review_finding(finding_id: str, body: ReviewCreate,
                   ctx=Depends(require_case({"reviewer", "owner"})),
                   db: Session = Depends(get_db)):
    finding = db.get(Finding, finding_id)
    if finding is None or finding.case_id != ctx.case.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Finding not found")
    finding.review_status = body.decision
    finding.review_note = body.note
    finding.reviewed_by = ctx.user.id
    from ..models import utcnow
    finding.reviewed_at = utcnow()
    record(db, ctx.user.id, "finding.review", "finding", finding_id, ctx.case.id,
           {"decision": body.decision})
    db.commit()
    return {"id": finding.id, "review_status": finding.review_status}


@router.get("/evidence/{evidence_id}")
def get_evidence(evidence_id: str, ctx=Depends(require_case()), db: Session = Depends(get_db)):
    record = db.get(EvidenceRecord, evidence_id)
    if record is None or record.case_id != ctx.case.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found")
    return {
        "id": record.id, "source_url": record.source_url, "method": record.method,
        "object_hash": record.object_hash, "snapshot_key": record.snapshot_key,
        "source_kind": record.source_kind, "allowed_use": json.loads(record.allowed_use),
        "timestamp_provenance": json.loads(record.timestamp_provenance),
        "input_id": record.input_id, "note": record.note,
    }


@router.get("/stats")
def case_stats(ctx=Depends(require_case()), db: Session = Depends(get_db)):
    cid = ctx.case.id
    def count(model):
        return db.scalar(select(func.count()).select_from(model).where(
            model.case_id == cid))
    return {
        "accounts": count(Account),
        "posts": count(Post),
        "comments": count(Comment),
        "media": count(MediaAsset),
        "findings": count(Finding),
        "analyzed_comments": count(CommentAnalysis),
    }
