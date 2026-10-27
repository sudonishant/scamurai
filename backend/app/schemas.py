"""Validated request/response contracts (master prompt section 17)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


# --------------------------------------------------------------------------- auth/cases
class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role_hint: str = "development user"


class CaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    purpose: str = ""
    allowed_sources: list[str] = Field(default_factory=list)
    date_from: datetime | None = None
    date_to: datetime | None = None
    languages: list[str] = Field(default_factory=lambda: ["en", "hi"])
    retention_days: int | None = Field(default=None, ge=1, le=3650)
    limits: dict[str, Any] = Field(default_factory=dict)
    member_emails: list[str] = Field(default_factory=list)
    member_roles: dict[str, str] = Field(default_factory=dict)


class CaseOut(BaseModel):
    id: str
    title: str
    purpose: str
    allowed_sources: list[str]
    date_from: datetime | None
    date_to: datetime | None
    languages: list[str]
    retention_days: int | None
    limits: dict[str, Any]
    my_role: str
    created_at: datetime


# --------------------------------------------------------------------------- inputs
class UrlInputCreate(BaseModel):
    url: str
    kind: Literal["url", "account"] = "url"
    platform: str | None = None
    note: str | None = None

    @field_validator("url")
    @classmethod
    def _basic_shape(cls, v: str) -> str:
        v = v.strip()
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class TextInputCreate(BaseModel):
    text: str = Field(min_length=1, max_length=50_000)
    language: str = "und"
    context_url: str | None = None


class InputOut(BaseModel):
    id: str
    kind: str
    status: str
    filename: str | None
    content_type: str | None
    byte_length: int | None
    payload: dict[str, Any]
    source_access: list[dict[str, Any]] = Field(default_factory=list)
    replayed: bool = False
    created_at: datetime


class CapabilityOut(BaseModel):
    provider: str
    configured: bool
    operations: list[str]
    status: str  # configured|not_configured|access_required|import_available
    detail: str


# --------------------------------------------------------------------------- runs / jobs
class RunCreate(BaseModel):
    workflow: Literal[
        "import_pipeline",
        "image_matching",
        "comment_analysis",
        "coordination_detection",
        "claim_workflow",
        "location_analysis",
        "media_forensics",
    ]
    input_ids: list[str] = Field(default_factory=list)
    date_range: dict[str, datetime | None] = Field(default_factory=dict)
    allowed_provider_ids: list[str] = Field(default_factory=list)
    limits: dict[str, Any] = Field(default_factory=dict)
    client_idempotency_key: str = Field(min_length=8, max_length=200)


class TransformCreate(BaseModel):
    transform: str
    entity_type: str
    entity_id: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    client_idempotency_key: str = Field(min_length=8, max_length=200)


class JobOut(BaseModel):
    id: str
    run_id: str | None
    kind: str
    lifecycle: str
    outcome: str | None
    stage: str
    counts: dict[str, Any]
    limitations: list[Any]
    warnings: list[Any]
    error: str | None
    cancel_requested: bool
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    retryable: bool = False


class JobEventOut(BaseModel):
    seq: int
    event_type: str
    payload: dict[str, Any]
    created_at: datetime


# --------------------------------------------------------------------------- graph
class GraphOut(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    truncated: bool
    total_nodes: int
    total_edges: int


class PathRequest(BaseModel):
    source_node_id: str
    target_node_id: str
    max_depth: int = Field(default=6, ge=1, le=12)
    max_nodes: int = Field(default=50, ge=1, le=200)


# --------------------------------------------------------------------------- comments / findings
class CommentOut(BaseModel):
    id: str
    stable_id: str | None
    raw_text: str
    author_ref: str
    timestamp: datetime | None
    timestamp_precision: str
    parent_comment_id: str | None
    permalink: str | None
    permalink_status: str
    review_status: str
    uncertain_duplicate: bool
    analysis: dict[str, Any] | None = None


class ReviewCreate(BaseModel):
    decision: Literal["accepted", "rejected", "needs_more_evidence"]
    note: str = ""


class AlertReview(BaseModel):
    status: Literal["open", "acknowledged", "resolved", "dismissed"]
    note: str = Field(default="", max_length=4000)


class FindingOut(BaseModel):
    id: str
    question: str
    conclusion_category: str
    evidence_ids: list[str]
    excerpts: list[Any]
    limitations: list[Any]
    contradictions: list[Any]
    review_status: str
    review_note: str | None
    analysis_run_id: str | None
    created_at: datetime


# --------------------------------------------------------------------------- exports
class ExportCreate(BaseModel):
    fmt: Literal["pdf", "json", "csv", "html"]
    scope: Literal["all", "selected", "flagged"] = "all"
    redaction_mode: Literal["redacted", "full"] = "redacted"
    selected_ids: list[str] = Field(default_factory=list)


class ExportOut(BaseModel):
    id: str
    fmt: str
    scope: str
    redaction_mode: str
    status: str
    sha256: str | None
    expires_at: datetime | None
    created_at: datetime
    download_url: str | None = None
