"""On-demand explainable campaign analytics for the collected case corpus."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import require_case
from ..services.analytics import build_analytics

router = APIRouter(prefix="/api/v1/cases/{case_id}/analytics", tags=["analytics"])


@router.get("")
def analytics(ctx=Depends(require_case()), db: Session = Depends(get_db)):
    return build_analytics(db, ctx.case.id)
