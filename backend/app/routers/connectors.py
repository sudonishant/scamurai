"""Live provider connector endpoints (disabled/honest until a key is configured)."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import EvidenceRecord, SourceAccess
from ..security import require_case
from ..services import graph, importer, storage
from ..services.providers import factcheck as fc_provider
from ..services.providers import mastodon as mastodon_provider
from ..services.providers import telegram as tg_provider
from ..services.providers import youtube as yt_provider

router = APIRouter(prefix="/api/v1/cases/{case_id}/connectors", tags=["connectors"])


class YouTubeImport(BaseModel):
    url: str = Field(min_length=11, max_length=2000)
    max_pages: int = Field(default=3, ge=1, le=10)


class MastodonImport(BaseModel):
    instance: str = Field(min_length=3, max_length=300)
    hashtag: str = Field(min_length=1, max_length=100)
    limit: int = Field(default=40, ge=1, le=40)


class FactCheckQuery(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    language_code: str | None = None
    max_age_days: int | None = Field(default=None, ge=1, le=3650)


@router.post("/youtube/import", status_code=201)
def youtube_import(body: YouTubeImport,
                   ctx=Depends(require_case({"analyst", "owner"})),
                   db: Session = Depends(get_db)):
    """Import public YouTube comments through the official Data API v3.

    Bounded pagination; commentsDisabled/quota errors become explicit
    SourceAccess outcomes instead of empty-result claims.
    """
    try:
        result = yt_provider.fetch_youtube_comments(body.url, max_pages=body.max_pages)
    except yt_provider.YouTubeError as exc:
        db.add(SourceAccess(
            case_id=ctx.case.id, provider="youtube", method="commentThreads.list",
            capability="comments:read", outcome=exc.outcome, detail=exc.detail))
        db.commit()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY,
                            f"{exc.outcome}: {exc.detail}") from exc

    # The API does not provide a comparable platform-displayed total, so the
    # coverage statement stays honest: denominator unknown/uncomparable.
    meta = {"platform": "youtube", "counts_comparable": False,
            "platform_displayed_count": None,
            "quota_units_used": result.quota_units,
            "pages_fetched": result.pages_fetched}
    summary = importer.import_comment_rows(
        db, ctx.case.id, ctx.user.id, result.comments, meta, input_id=None)
    db.add(SourceAccess(
        case_id=ctx.case.id, provider="youtube", method="commentThreads.list",
        capability="comments:read", outcome=result.outcome,
        detail=json.dumps({"video_id": result.video_id, **summary, **meta})))
    db.commit()
    return {"video_id": result.video_id, **summary}


@router.post("/mastodon/import", status_code=201)
def mastodon_import(body: MastodonImport,
                    ctx=Depends(require_case({"analyst", "owner"})),
                    db: Session = Depends(get_db)):
    """Import one bounded public hashtag page through the instance's official API."""
    try:
        result = mastodon_provider.fetch_public_hashtag(body.instance, body.hashtag, body.limit)
    except mastodon_provider.MastodonError as exc:
        code = 422 if exc.outcome == "validation_error" else 502
        db.add(SourceAccess(case_id=ctx.case.id, provider="mastodon", method="timelines.tag",
                            capability="public_posts:read", outcome=exc.outcome, detail=exc.detail))
        db.commit()
        raise HTTPException(status_code=code, detail=f"{exc.outcome}: {exc.detail}") from exc

    raw = result["raw"].encode("utf-8")
    evidence = EvidenceRecord(
        case_id=ctx.case.id, source_url=result["source_url"], method="mastodon_public_api_v1",
        object_hash=storage.sha256_hex(raw), source_kind="public_api_snapshot",
        note=result["coverage_note"],
    )
    db.add(evidence)
    db.flush()
    key = storage.put_object(ctx.case.id, f"mastodon/{evidence.id}.json", raw)
    evidence.snapshot_key = key
    graph.evidence_node(db, evidence)
    counts = importer.import_posts_bundle(db, ctx.case.id, ctx.user.id, result["bundle"], None)
    outcome = "successful" if counts["posts"] else "successful_empty"
    db.add(SourceAccess(
        case_id=ctx.case.id, provider=f"mastodon:{result['instance']}", method="timelines.tag",
        capability="public_posts:read", outcome=outcome,
        detail=json.dumps({"hashtag": result["hashtag"], "statuses_returned": result["statuses_returned"],
                           "skipped_reblogs": result["skipped_reblogs"], **counts,
                           "coverage": result["coverage_note"]})))
    db.commit()
    return {"instance": result["instance"], "hashtag": result["hashtag"],
            "statuses_returned": result["statuses_returned"],
            "skipped_reblogs": result["skipped_reblogs"], "evidence_id": evidence.id,
            **counts, "coverage": result["coverage_note"]}


@router.post("/factcheck/search")
def factcheck_search(body: FactCheckQuery,
                     ctx=Depends(require_case({"analyst", "owner"}))):
    """Live Google Fact Check search. Empty list = no published fact-check found,
    never proof that the claim is false."""
    try:
        matches = fc_provider.search_factchecks(
            body.query, language_code=body.language_code, max_age_days=body.max_age_days)
    except fc_provider.FactCheckError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY,
                            f"{exc.outcome}: {exc.detail}") from exc
    return {"query": body.query, "matches": matches,
            "note": "No result means no matching published fact-check, not that the claim is false."}


class TelegramImport(BaseModel):
    channel: str = Field(min_length=2, max_length=200)
    limit: int = Field(default=40, ge=1, le=100)


@router.post("/telegram/import", status_code=201)
def telegram_import(body: TelegramImport,
                    ctx=Depends(require_case({"analyst", "owner"})),
                    db: Session = Depends(get_db)):
    """Zero-API OSINT Import from public Telegram channels.
    Extracts posts, timestamps, views, forwards and embedded IoCs.
    """
    try:
        result = tg_provider.fetch_public_channel(body.channel, limit=body.limit)
    except tg_provider.TelegramError as exc:
        db.add(SourceAccess(
            case_id=ctx.case.id, provider=f"telegram:{body.channel}", method="web.preview",
            capability="public_channel:read", outcome=exc.outcome, detail=exc.detail))
        db.commit()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"{exc.outcome}: {exc.detail}")

    raw = json.dumps(result, ensure_ascii=False).encode("utf-8")
    evidence = EvidenceRecord(
        case_id=ctx.case.id, collected_by=ctx.user.id, source_url=result["source_url"],
        object_hash=storage.sha256_hex(raw), source_kind="public_channel_snapshot",
        note=f"Public Telegram OSINT import from @{result['channel']}",
    )
    db.add(evidence)
    db.flush()
    key = storage.put_object(ctx.case.id, f"telegram/{evidence.id}.json", raw)
    evidence.snapshot_key = key
    graph.evidence_node(db, evidence)
    counts = importer.import_posts_bundle(db, ctx.case.id, ctx.user.id, result["bundle"], None)
    outcome = "successful" if counts["posts"] else "successful_empty"
    db.add(SourceAccess(
        case_id=ctx.case.id, provider=f"telegram:{result['channel']}", method="web.preview",
        capability="public_channel:read", outcome=outcome,
        detail=json.dumps({"channel": result["channel"], **counts})))
    db.commit()
    return {"channel": result["channel"], "evidence_id": evidence.id,
            "posts_returned": result["posts_count"], **counts}

