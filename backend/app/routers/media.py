"""Media-forensics history; every model result remains separate from observations."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import MediaAsset, MediaForensics
from ..security import require_case

router = APIRouter(prefix="/api/v1/cases/{case_id}/media", tags=["media"])


def _serialize(row: MediaForensics, asset: MediaAsset | None) -> dict:
    return {
        "id": row.id,
        "media_asset_id": row.media_asset_id,
        "analysis_run_id": row.analysis_run_id,
        "status": row.status,
        "filename": asset.filename if asset else "unavailable",
        "sha256": asset.sha256 if asset else None,
        "phash": asset.phash if asset else None,
        "mime_type": asset.mime_type if asset else None,
        "width": asset.width if asset else None,
        "height": asset.height if asset else None,
        "indicators": json.loads(row.indicators),
        "model_result": json.loads(row.model_result),
        "limitations": json.loads(row.limitations),
        "created_at": row.created_at.isoformat(),
    }


@router.get("/forensics")
def list_forensics(ctx=Depends(require_case()), db: Session = Depends(get_db)):
    rows = db.scalars(select(MediaForensics).where(MediaForensics.case_id == ctx.case.id)
                      .order_by(MediaForensics.created_at.desc()).limit(200)).all()
    return [_serialize(row, db.get(MediaAsset, row.media_asset_id)) for row in rows]


@router.get("/forensics/{forensics_id}")
def get_forensics(forensics_id: str, ctx=Depends(require_case()), db: Session = Depends(get_db)):
    row = db.get(MediaForensics, forensics_id)
    if row is None or row.case_id != ctx.case.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Media forensics result not found")
    return _serialize(row, db.get(MediaAsset, row.media_asset_id))
