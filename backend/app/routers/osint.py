"""Public-infrastructure OSINT reports with immutable evidence snapshots."""
from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import EvidenceRecord, OsintReport, SourceAccess
from ..security import require_case
from ..services import graph, storage
from ..services.audit import record
from ..services.osint import investigate

router = APIRouter(prefix="/api/v1/cases/{case_id}/osint", tags=["osint"])


class InvestigationCreate(BaseModel):
    target: str = Field(min_length=1, max_length=2048)
    modules: list[str] | None = Field(default=None, max_length=5)


def _summary(row: OsintReport) -> dict:
    payload = json.loads(row.report)
    return {
        "id": row.id,
        "target": row.target,
        "target_type": row.target_type,
        "status": row.status,
        "summary": payload.get("summary", {}),
        "modules": [{"module": m.get("module"), "status": m.get("status")} for m in payload.get("modules", [])],
        "object_hash": row.object_hash,
        "created_at": row.created_at.isoformat(),
    }


@router.post("/investigate", status_code=status.HTTP_201_CREATED)
def create_investigation(
    body: InvestigationCreate,
    ctx=Depends(require_case({"analyst", "owner"})),
    db: Session = Depends(get_db),
):
    try:
        payload = investigate(body.target, body.modules)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    raw = canonical.encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    key = storage.put_object(ctx.case.id, f"osint/{digest}.json", raw)
    evidence = EvidenceRecord(
        case_id=ctx.case.id,
        source_url=payload.get("normalized_target"),
        method="bounded_public_source_osint_v1",
        object_hash=digest,
        snapshot_key=key,
        source_kind="osint_report",
        note="Source-attributed infrastructure observations; module failures are preserved, never replaced with synthetic values.",
        timestamp_provenance=json.dumps({"collected_at": payload["generated_at"], "source_clock": "per-module provider responses"}),
    )
    db.add(evidence)
    db.flush()
    graph.evidence_node(db, evidence)
    row = OsintReport(
        case_id=ctx.case.id,
        target=payload["target"],
        target_type=payload["target_type"],
        status=payload["status"],
        report=json.dumps(payload, ensure_ascii=False),
        object_hash=digest,
        created_by=ctx.user.id,
    )
    db.add(row)
    db.flush()
    for module in payload["modules"]:
        db.add(SourceAccess(
            case_id=ctx.case.id,
            provider=f"osint:{module['module']}",
            method="bounded_public_api",
            capability="public_infrastructure:read",
            outcome=module["status"],
            detail=json.dumps({"error": module.get("error"), "collected_at": module.get("collected_at")}),
        ))
    record(db, ctx.user.id, "osint.investigate", "osint_report", row.id, ctx.case.id,
           {"target_type": row.target_type, "status": row.status, "modules": [m["module"] for m in payload["modules"]]})
    db.commit()
    return {"id": row.id, "evidence_id": evidence.id, **payload}


@router.get("/reports")
def list_reports(ctx=Depends(require_case()), db: Session = Depends(get_db)):
    rows = db.scalars(select(OsintReport).where(OsintReport.case_id == ctx.case.id)
                      .order_by(OsintReport.created_at.desc()).limit(100)).all()
    return [_summary(row) for row in rows]


@router.get("/reports/{report_id}")
def get_report(report_id: str, ctx=Depends(require_case()), db: Session = Depends(get_db)):
    row = db.get(OsintReport, report_id)
    if row is None or row.case_id != ctx.case.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "OSINT report not found")
    return {"id": row.id, "object_hash": row.object_hash, **json.loads(row.report)}


@router.get("/reports/{report_id}/download")
def download_report(report_id: str, ctx=Depends(require_case()), db: Session = Depends(get_db)):
    row = db.get(OsintReport, report_id)
    if row is None or row.case_id != ctx.case.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "OSINT report not found")
    canonical = json.dumps(json.loads(row.report), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return Response(
        content=canonical,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="scamurai-osint-{row.id[:8]}.json"',
            "X-Content-SHA256": row.object_hash,
        },
    )
