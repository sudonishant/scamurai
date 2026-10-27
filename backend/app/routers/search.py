"""Bounded, case-scoped global search. No cross-case read-all exists."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Account, Alert, EvidenceRecord, Finding, Post
from ..security import require_case

router = APIRouter(prefix="/api/v1/cases/{case_id}/search", tags=["search"])


def _pattern(query: str) -> str:
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@router.get("")
def search(q: str = Query(min_length=2, max_length=200),
           ctx=Depends(require_case()), db: Session = Depends(get_db)):
    query = q.strip()
    if len(query) < 2:
        return {"query": query, "total": 0, "groups": [], "scope": "current case only"}
    pattern = _pattern(query)
    groups = []

    rows = db.scalars(select(Account).where(
        Account.case_id == ctx.case.id,
        (Account.handle.ilike(pattern, escape="\\")) |
        (Account.display_name.ilike(pattern, escape="\\")) |
        (Account.platform.ilike(pattern, escape="\\")),
    ).order_by(Account.handle).limit(12)).all()
    if rows:
        groups.append({"type": "accounts", "items": [{
            "id": row.id, "title": f"@{row.handle}",
            "snippet": f"{row.platform} · {row.display_name or 'No display name'}",
            "target": {"tab": "accounts", "account": row.id},
        } for row in rows]})

    rows = db.scalars(select(Post).where(
        Post.case_id == ctx.case.id,
        (Post.raw_text.ilike(pattern, escape="\\")) |
        (Post.canonical_url.ilike(pattern, escape="\\")) |
        (Post.source_id.ilike(pattern, escape="\\")),
    ).order_by(Post.created_at.desc()).limit(12)).all()
    if rows:
        groups.append({"type": "posts", "items": [{
            "id": row.id, "title": row.source_id or "Collected post",
            "snippet": row.raw_text[:260] or row.canonical_url or "No text",
            "target": {"tab": "narratives", "post": row.id},
        } for row in rows]})

    rows = db.scalars(select(Alert).where(
        Alert.case_id == ctx.case.id,
        (Alert.title.ilike(pattern, escape="\\")) | (Alert.rule.ilike(pattern, escape="\\")),
    ).order_by(Alert.last_seen_at.desc()).limit(12)).all()
    if rows:
        groups.append({"type": "alerts", "items": [{
            "id": row.id, "title": row.title,
            "snippet": f"{row.severity} · {row.status} · {row.rule[:180]}",
            "target": {"tab": "alerts", "alert": row.id},
        } for row in rows]})

    rows = db.scalars(select(Finding).where(
        Finding.case_id == ctx.case.id,
        (Finding.question.ilike(pattern, escape="\\")) |
        (Finding.conclusion_category.ilike(pattern, escape="\\")),
    ).order_by(Finding.created_at.desc()).limit(12)).all()
    if rows:
        groups.append({"type": "findings", "items": [{
            "id": row.id, "title": row.conclusion_category.replace("_", " "),
            "snippet": row.question[:260],
            "target": {"tab": "findings", "finding": row.id},
        } for row in rows]})

    rows = db.scalars(select(EvidenceRecord).where(
        EvidenceRecord.case_id == ctx.case.id,
        (EvidenceRecord.source_url.ilike(pattern, escape="\\")) |
        (EvidenceRecord.method.ilike(pattern, escape="\\")) |
        (EvidenceRecord.object_hash.ilike(pattern, escape="\\")),
    ).order_by(EvidenceRecord.created_at.desc()).limit(12)).all()
    if rows:
        groups.append({"type": "evidence", "items": [{
            "id": row.id, "title": row.source_kind or "Evidence record",
            "snippet": f"{row.method} · {row.source_url or row.object_hash or 'no external URL'}",
            "target": {"tab": "graph", "evidence": row.id},
        } for row in rows]})

    return {
        "query": query,
        "total": sum(len(group["items"]) for group in groups),
        "groups": groups,
        "scope": "Current case only; results are bounded to 12 per entity class.",
    }
