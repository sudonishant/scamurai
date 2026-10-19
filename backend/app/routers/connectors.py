"""Live provider connector endpoints (disabled/honest until a key is configured)."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import SourceAccess
from ..security import require_case
from ..services import importer
from ..services.providers import factcheck as fc_provider
from ..services.providers import youtube as yt_provider

router = APIRouter(prefix="/api/v1/cases/{case_id}/connectors", tags=["connectors"])


class YouTubeImport(BaseModel):
    url: str = Field(min_length=11, max_length=2000)
    max_pages: int = Field(default=3, ge=1, le=10)


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
                            f"{exc.outcome}: {exc.detail}")

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
                            f"{exc.outcome}: {exc.detail}")
    return {"query": body.query, "matches": matches,
            "note": "No result means no matching published fact-check, not that the claim is false."}
