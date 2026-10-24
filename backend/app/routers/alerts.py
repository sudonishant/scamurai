"""Persistent alert queue and audited analyst review decisions."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Alert, utcnow
from ..schemas import AlertReview
from ..security import require_case
from ..services.alerts import list_alerts, serialize
from ..services.audit import record

router = APIRouter(prefix="/api/v1/cases/{case_id}/alerts", tags=["alerts"])


@router.get("")
def alerts(active: bool | None = Query(default=None),
           ctx=Depends(require_case()), db: Session = Depends(get_db)):
    return list_alerts(db, ctx.case.id, active)


@router.post("/{alert_id}/review")
def review_alert(alert_id: str, body: AlertReview,
                 ctx=Depends(require_case({"reviewer", "owner"})),
                 db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if alert is None or alert.case_id != ctx.case.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    previous = alert.status
    alert.status = body.status
    alert.review_note = body.note.strip() or None
    alert.reviewed_by = ctx.user.id
    alert.reviewed_at = utcnow()
    record(db, ctx.user.id, "alert.review", "alert", alert.id, ctx.case.id,
           {"from": previous, "to": body.status})
    db.commit()
    return serialize(alert)
