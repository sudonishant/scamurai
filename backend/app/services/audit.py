"""Audit trail: who imported, expanded, merged, reviewed and exported what."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from ..models import AuditEvent


def record(
    db: Session, actor_id: str | None, action: str,
    target_type: str = "", target_id: str = "",
    case_id: str | None = None, detail: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        case_id=case_id, actor_id=actor_id, action=action,
        target_type=target_type, target_id=target_id,
        detail=json.dumps(detail or {}),
    )
    db.add(event)
    db.flush()
    return event
