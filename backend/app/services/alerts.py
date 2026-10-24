"""Durable alert materialization and analyst workflow state."""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Alert, utcnow


def _loads(value: str, fallback):
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def serialize(alert: Alert) -> dict:
    payload = _loads(alert.payload, {})
    payload.update({
        "id": alert.id,
        "rule_id": alert.dedup_key,
        "type": alert.alert_type,
        "title": alert.title,
        "severity": alert.severity,
        "status": alert.status,
        "active": alert.active,
        "attention_score": alert.attention_score,
        "score_type": alert.score_type,
        "rule": alert.rule,
        "narrative_id": alert.narrative_id,
        "evidence_ids": _loads(alert.evidence_ids, []),
        "recommended_action": alert.recommended_action,
        "limitations": _loads(alert.limitations, []),
        "first_seen_at": alert.first_seen_at.isoformat() if alert.first_seen_at else None,
        "last_seen_at": alert.last_seen_at.isoformat() if alert.last_seen_at else None,
        "review_note": alert.review_note,
        "reviewed_by": alert.reviewed_by,
        "reviewed_at": alert.reviewed_at.isoformat() if alert.reviewed_at else None,
    })
    return payload


def _sort(rows: list[Alert]) -> list[Alert]:
    severity = {"high": 4, "elevated": 3, "review": 2, "data_gap": 1}
    return sorted(rows, key=lambda row: (
        row.active,
        row.status not in {"resolved", "dismissed"},
        severity.get(row.severity, 0),
        row.attention_score or 0,
        row.last_seen_at,
    ), reverse=True)


def sync_alerts(db: Session, case_id: str, derived: list[dict]) -> list[dict]:
    """Refresh derived fields without erasing human review decisions."""
    rows = db.scalars(select(Alert).where(Alert.case_id == case_id)).all()
    existing = {row.dedup_key: row for row in rows}
    seen = set()
    now = utcnow()
    for item in derived:
        dedup_key = str(item.get("id") or "")[:200]
        if not dedup_key:
            continue
        seen.add(dedup_key)
        row = existing.get(dedup_key)
        if row is None:
            row = Alert(case_id=case_id, dedup_key=dedup_key, alert_type=str(item.get("type") or "review"),
                        title=str(item.get("title") or "Review cue"), first_seen_at=now)
            db.add(row)
            existing[dedup_key] = row
        row.alert_type = str(item.get("type") or "review")
        row.title = str(item.get("title") or "Review cue")
        row.severity = str(item.get("severity") or "review")
        row.active = True
        row.attention_score = (float(item["attention_score"])
                               if item.get("attention_score") is not None else None)
        row.score_type = str(item.get("score_type") or "not_applicable")
        row.rule = str(item.get("rule") or "")
        row.narrative_id = item.get("narrative_id")
        row.evidence_ids = json.dumps(item.get("evidence_ids") or [])
        row.recommended_action = str(item.get("recommended_action") or "")
        row.limitations = json.dumps(item.get("limitations") or [])
        row.payload = json.dumps(item)
        row.last_seen_at = now
    for row in rows:
        if row.dedup_key not in seen:
            row.active = False
    db.commit()
    active = [row for row in existing.values() if row.active]
    return [serialize(row) for row in _sort(active)]


def list_alerts(db: Session, case_id: str, active: bool | None = None) -> list[dict]:
    query = select(Alert).where(Alert.case_id == case_id)
    if active is not None:
        query = query.where(Alert.active == active)
    rows = db.scalars(query).all()
    return [serialize(row) for row in _sort(list(rows))]
