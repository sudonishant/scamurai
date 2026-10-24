"""Cases, inputs, authorized uploads, capabilities and audit (sections 4, 8, 17)."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import (
    AuditEvent, Case, CaseMembership, EvidenceRecord, Input, Post, SourceAccess, User,
)
from ..registry import POST
from ..schemas import CapabilityOut, CaseCreate, CaseOut, InputOut, TextInputCreate, UrlInputCreate
from ..security import get_current_user, require_case, validate_image_signature
from ..services import connectors, graph, importer, storage
from ..services.audit import record
from ..services.textutil import normalize_text

router = APIRouter(prefix="/api/v1", tags=["cases"])
settings = get_settings()


def _serialize_case(case: Case, role: str) -> CaseOut:
    return CaseOut(
        id=case.id, title=case.title, purpose=case.purpose,
        allowed_sources=json.loads(case.allowed_sources),
        date_from=case.date_from, date_to=case.date_to,
        languages=json.loads(case.languages), retention_days=case.retention_days,
        limits=json.loads(case.limits), my_role=role, created_at=case.created_at,
    )


@router.get("/users", response_model=list[dict])
def list_users(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # The development role picker is never a production user directory.
    rows = db.scalars(select(User)).all() if settings.dev_auth_enabled else [user]
    return [{"id": row.id, "email": row.email, "name": row.name,
             "token_hint": row.dev_token if settings.dev_auth_enabled else None}
            for row in rows]


@router.post("/cases", response_model=CaseOut, status_code=201)
def create_case(body: CaseCreate, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    # Policy guardrails are clamped server-side even if the client asks for more.
    defaults = {"max_seed_urls": settings.max_seed_urls, "max_depth": settings.max_depth,
                "max_new_entities": settings.max_new_entities,
                "max_source_fetches": settings.max_source_fetches,
                "run_deadline_seconds": settings.run_deadline_seconds}
    clamped = {**defaults, **body.limits}
    case = Case(
        title=body.title, purpose=body.purpose,
        allowed_sources=json.dumps(body.allowed_sources),
        date_from=body.date_from, date_to=body.date_to,
        languages=json.dumps(body.languages), retention_days=body.retention_days,
        limits=json.dumps(clamped), created_by=user.id,
    )
    db.add(case)
    db.flush()
    db.add(CaseMembership(case_id=case.id, user_id=user.id, role="owner"))
    for email in body.member_emails:
        other = db.scalar(select(User).where(User.email == email))
        if other:
            m_role = body.member_roles.get(email, "viewer")
            db.add(CaseMembership(case_id=case.id, user_id=other.id, role=m_role))
    record(db, user.id, "case.create", "case", case.id, case.id, {"title": case.title})
    db.commit()
    return _serialize_case(case, "owner")


@router.get("/cases", response_model=list[CaseOut])
def list_cases(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    memberships = db.scalars(select(CaseMembership).where(
        CaseMembership.user_id == user.id)).all()
    out = []
    for m in memberships:
        case = db.get(Case, m.case_id)
        if case:
            out.append(_serialize_case(case, m.role))
    return out


@router.get("/cases/{case_id}", response_model=CaseOut)
def get_case(ctx=Depends(require_case()), db: Session = Depends(get_db)):
    return _serialize_case(ctx.case, ctx.role)


@router.get("/cases/{case_id}/capabilities", response_model=list[CapabilityOut])
def capabilities(ctx=Depends(require_case())):
    return [CapabilityOut(**c.as_dict()) for c in connectors.check_capabilities()]


# --------------------------------------------------------------------- inputs
@router.post("/cases/{case_id}/inputs", response_model=InputOut, status_code=201)
def create_input(body: UrlInputCreate | TextInputCreate,
                 ctx=Depends(require_case({"analyst", "owner"})),
                 db: Session = Depends(get_db)):
    case = ctx.case
    idem = f"input:{body.__class__.__name__}:{getattr(body, 'url', '') or getattr(body, 'text', '')[:80]}"
    existing = db.scalar(select(Input).where(
        Input.case_id == case.id, Input.idempotency_key == idem))
    if existing:
        return _serialize_input(db, existing)

    if isinstance(body, UrlInputCreate):
        # SSRF policy is enforced before the input is even accepted.
        from ..security import assert_public_url
        assert_public_url(body.url)
        inp = Input(case_id=case.id, kind=body.kind,
                    payload=json.dumps({"url": body.url, "platform": body.platform,
                                        "note": body.note}),
                    idempotency_key=idem, created_by=ctx.user.id, status="preflight_ok")
        db.add(inp)
        db.flush()
        provider = connectors.provider_for_url(body.url)
        caps = {c.provider: c for c in connectors.check_capabilities()}
        cap = caps.get(provider)
        outcome = "not_configured" if cap and not cap.configured else "pending_fetch"
        db.add(SourceAccess(case_id=case.id, input_id=inp.id, provider=provider,
                            method="preflight", capability="fetch_post", outcome=outcome,
                            detail=cap.detail if cap else "Awaiting bounded run"))
    else:
        inp = Input(case_id=case.id, kind="text",
                    payload=json.dumps({"text": body.text, "language": body.language}),
                    idempotency_key=idem, created_by=ctx.user.id)
        db.add(inp)
        db.flush()
        # Pasted post text becomes a normal, reviewable Post record with honest status.
        post = Post(case_id=case.id, source_id=f"manual-{inp.id[:8]}",
                    canonical_url=body.context_url, raw_text=body.text,
                    normalized_text=normalize_text(body.text), language=body.language,
                    collection_status="manual_text_input", timestamp_precision="unknown")
        db.add(post)
        db.flush()
        graph.upsert_node(db, case.id, POST, post.id, body.text[:80],
                          {"source_id": post.source_id})
        evidence = EvidenceRecord(case_id=case.id, input_id=inp.id,
                                  source_url=body.context_url, method="manual_entry",
                                  source_kind="snippet", note="User-pasted text; not a platform record")
        db.add(evidence)
        db.flush()
        graph.evidence_node(db, evidence)
    record(db, ctx.user.id, "input.create", "input", inp.id, case.id)
    db.commit()
    return _serialize_input(db, inp)


@router.post("/cases/{case_id}/uploads", response_model=InputOut, status_code=201)
async def upload(
    response: Response,
    ctx=Depends(require_case({"analyst", "owner"})),
    file: UploadFile = File(...),
    kind: str = Form(...),  # image | csv | json
    meta: str = Form(default="{}"),
    db: Session = Depends(get_db),
):
    raw = await file.read()
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Upload exceeds case limit")
    idempotency_key = f"upload:{storage.sha256_hex(raw)}:{file.filename}"
    existing = db.scalar(select(Input).where(
        Input.case_id == ctx.case.id, Input.idempotency_key == idempotency_key))
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return _serialize_input(db, existing, replayed=True)
    inp = Input(case_id=ctx.case.id, kind=kind, filename=file.filename,
                content_type=file.content_type, byte_length=len(raw),
                payload=json.dumps({"meta": meta}), created_by=ctx.user.id,
                idempotency_key=idempotency_key)
    db.add(inp)
    db.flush()
    try:
        if kind == "image":
            mime = validate_image_signature(raw)
            asset = importer.register_media(db, ctx.case.id, ctx.user.id, raw,
                                            file.filename, mime, inp.id)
            inp.status = f"media_registered:{asset.id[:8]}"
        elif kind == "json":
            payload = importer.parse_json(raw)
            importer._snapshot(db, ctx.case.id, inp.id, raw, "import", None)
            if isinstance(payload, dict) and "factchecks" in payload:
                key = storage.put_object(ctx.case.id, f"factchecks/{inp.id}.json", raw)
                fc_record = EvidenceRecord(case_id=ctx.case.id, input_id=inp.id,
                                           method="authorized_import", snapshot_key=key,
                                           source_kind="factcheck_import",
                                           object_hash=storage.sha256_hex(raw))
                db.add(fc_record)
                db.flush()
                graph.evidence_node(db, fc_record)
                inp.status = "factcheck_library_imported"
            elif isinstance(payload, dict) and ("accounts" in payload or "posts" in payload):
                counts = importer.import_posts_bundle(db, ctx.case.id, ctx.user.id, payload, inp.id)
                inp.status = f"posts_imported:{counts['posts']}"
            else:
                rows = payload["comments"] if isinstance(payload, dict) and "comments" in payload else payload
                meta_dict = json.loads(meta) if meta else {}
                if isinstance(payload, dict):
                    meta_dict = {**payload.get("meta", {}), **meta_dict}
                summary = importer.import_comment_rows(db, ctx.case.id, ctx.user.id, rows,
                                                       meta_dict, inp.id)
                inp.status = f"comments_imported:{summary['comments_created']}"
        elif kind == "csv":
            rows = importer.parse_csv(raw)
            importer._snapshot(db, ctx.case.id, inp.id, raw, "import", None)
            summary = importer.import_comment_rows(
                db, ctx.case.id, ctx.user.id, rows, json.loads(meta or "{}"), inp.id)
            inp.status = f"comments_imported:{summary['comments_created']}"
        else:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unsupported upload kind")
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    record(db, ctx.user.id, "input.upload", "input", inp.id, ctx.case.id,
           {"filename": file.filename, "bytes": len(raw)})
    db.commit()
    return _serialize_input(db, inp)


def _serialize_input(db: Session, inp: Input, replayed: bool = False) -> InputOut:
    access = db.scalars(select(SourceAccess).where(SourceAccess.input_id == inp.id)).all()
    return InputOut(
        id=inp.id, kind=inp.kind, status=inp.status, filename=inp.filename,
        content_type=inp.content_type, byte_length=inp.byte_length,
        payload=json.loads(inp.payload),
        source_access=[{"provider": a.provider, "outcome": a.outcome, "detail": a.detail,
                        "checked_at": a.checked_at.isoformat()} for a in access],
        replayed=replayed,
        created_at=inp.created_at,
    )


@router.get("/cases/{case_id}/audit")
def audit_log(ctx=Depends(require_case()), db: Session = Depends(get_db)):
    events = db.scalars(select(AuditEvent).where(
        AuditEvent.case_id == ctx.case.id).order_by(AuditEvent.created_at.desc())).all()
    return [{"id": e.id, "action": e.action, "target_type": e.target_type,
             "target_id": e.target_id, "detail": json.loads(e.detail),
             "created_at": e.created_at.isoformat()} for e in events]
