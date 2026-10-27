"""Exports with redaction modes, expiring links and artifact manifests."""
from __future__ import annotations

import json
from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Export, MediaAsset, utcnow
from ..schemas import ExportCreate, ExportOut
from ..security import require_case
from ..services import exports as export_svc
from ..services import storage
from ..services.audit import record

router = APIRouter(prefix="/api/v1/cases/{case_id}", tags=["exports"])

MEDIA_TYPES = {"pdf": "application/pdf", "json": "application/json",
               "csv": "text/csv", "html": "text/html"}


def _is_expired(export: Export) -> bool:
    if not export.expires_at:
        return False
    expires = export.expires_at
    if expires.tzinfo is None:  # SQLite returns naive datetimes; compare in UTC
        expires = expires.replace(tzinfo=UTC)
    return expires < utcnow()


@router.post("/exports", response_model=ExportOut, status_code=202)
def create_export(body: ExportCreate,
                  ctx=Depends(require_case({"analyst", "owner"})),
                  db: Session = Depends(get_db)):
    export = Export(
        case_id=ctx.case.id, scope=body.scope, redaction_mode=body.redaction_mode,
        fmt=body.fmt, created_by=ctx.user.id,
        manifest=json.dumps({"selected_ids": body.selected_ids}))
    db.add(export)
    db.flush()
    export_svc.run_export(db, ctx.case, export)
    record(db, ctx.user.id, "export.create", "export", export.id, ctx.case.id,
           {"fmt": body.fmt, "scope": body.scope, "mode": body.redaction_mode})
    db.commit()
    return _out(export)


@router.get("/exports", response_model=list[ExportOut])
def list_exports(ctx=Depends(require_case()), db: Session = Depends(get_db)):
    rows = db.scalars(select(Export).where(
        Export.case_id == ctx.case.id).order_by(Export.created_at.desc())).all()
    return [_out(e) for e in rows]


@router.get("/exports/{export_id}", response_model=ExportOut)
def get_export(export_id: str, ctx=Depends(require_case()), db: Session = Depends(get_db)):
    export = db.get(Export, export_id)
    if export is None or export.case_id != ctx.case.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Export not found")
    return _out(export)


@router.get("/exports/{export_id}/download")
def download(export_id: str, ctx=Depends(require_case()), db: Session = Depends(get_db)):
    export = db.get(Export, export_id)
    if export is None or export.case_id != ctx.case.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Export not found")
    if _is_expired(export):
        raise HTTPException(status.HTTP_410_GONE, "Download link expired; generate a new export")
    blob = storage.get_object(export.artifact_key)
    return Response(
        blob, media_type=MEDIA_TYPES[export.fmt],
        headers={"Content-Disposition": f'attachment; filename="scamurai-{export_id[:8]}.{export.fmt}"'})


@router.get("/media/{media_id}/raw")
def media_raw(media_id: str, ctx=Depends(require_case()), db: Session = Depends(get_db)):
    asset = db.get(MediaAsset, media_id)
    if asset is None or asset.case_id != ctx.case.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Media not found")
    blob = storage.get_object(asset.object_key)
    return Response(blob, media_type=asset.mime_type)


def _out(export: Export) -> ExportOut:
    expired = _is_expired(export)
    return ExportOut(
        id=export.id, fmt=export.fmt, scope=export.scope,
        redaction_mode=export.redaction_mode, status=export.status, sha256=export.sha256,
        expires_at=export.expires_at, created_at=export.created_at,
        download_url=None if expired else f"/api/v1/cases/{export.case_id}/exports/{export.id}/download")
