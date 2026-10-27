"""Evidence-first relational model (master prompt section 6).

Design rules enforced at the data layer:
* every entity gets an internal UUID, UTC timestamps and case ownership;
* raw source representations are kept separate from normalized/corrected fields;
* graph edges carry a derivation class (fact / similarity / hypothesis / note),
  so an LLM sentence can never silently become a source-supported relationship;
* derived analysis is versioned, never mutated in place; merge/split are
  reversible operations recorded as audit events instead of deletions.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Float,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def uuid_pk() -> Mapped[str]:
    return mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


# --------------------------------------------------------------------------- users / RBAC
class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("auth_issuer", "auth_subject", name="uq_user_oidc_subject"),)
    id: Mapped[str] = uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    # Development token only; production uses a pre-provisioned OIDC subject.
    dev_token: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    auth_issuer: Mapped[str | None] = mapped_column(String(512), nullable=True)
    auth_subject: Mapped[str | None] = mapped_column(String(512), nullable=True)


class Case(Base, TimestampMixin):
    __tablename__ = "cases"
    id: Mapped[str] = uuid_pk()
    title: Mapped[str] = mapped_column(String(300))
    purpose: Mapped[str] = mapped_column(Text, default="")
    allowed_sources: Mapped[str] = mapped_column(Text, default="[]")        # JSON list
    date_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    date_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    languages: Mapped[str] = mapped_column(String(300), default="[]")       # JSON list
    retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    limits: Mapped[str] = mapped_column(Text, default="{}")                 # JSON policy clamp
    schema_version: Mapped[str] = mapped_column(String(40), default="scamurai-0.1")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))

    memberships: Mapped[list[CaseMembership]] = relationship(cascade="all, delete-orphan")


class CaseMembership(Base):
    __tablename__ = "case_memberships"
    id: Mapped[str] = uuid_pk()
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    # owner > analyst > reviewer > viewer (see security.py ROLE_RANK)
    role: Mapped[str] = mapped_column(String(40))
    __table_args__ = (UniqueConstraint("case_id", "user_id", name="uq_case_user"),)


# --------------------------------------------------------------------------- inputs / access
class Input(Base, TimestampMixin):
    __tablename__ = "inputs"
    id: Mapped[str] = uuid_pk()
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # url|image|text|account|csv|json
    payload: Mapped[str] = mapped_column(Text, default="{}")                 # JSON
    filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    byte_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="received")
    idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    __table_args__ = (UniqueConstraint("case_id", "idempotency_key", name="uq_input_key"),)


class SourceAccess(Base):
    """Honest record of what an access attempt produced — never conflated with
    'nothing exists'."""
    __tablename__ = "source_access"
    id: Mapped[str] = uuid_pk()
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    input_id: Mapped[str | None] = mapped_column(ForeignKey("inputs.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(120), default="manual-import")
    method: Mapped[str] = mapped_column(String(120), default="authorized_import")
    capability: Mapped[str] = mapped_column(String(200), default="")
    # successful|successful_empty|not_supported|login_required|permission_denied|
    # rate_limited|unavailable|not_configured
    outcome: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(Text, default="")
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --------------------------------------------------------------------------- entities
class Account(Base, TimestampMixin):
    __tablename__ = "accounts"
    id: Mapped[str] = uuid_pk()
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(80))
    platform_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    handle: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255), default="")
    canonical_profile_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_handles: Mapped[str] = mapped_column(Text, default="[]")  # JSON history
    # A display-name match is never treated as a stable identity.
    identity_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)


class Post(Base, TimestampMixin):
    __tablename__ = "posts"
    id: Mapped[str] = uuid_pk()
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    normalized_text: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(String(24), default="und")
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    timestamp_precision: Mapped[str] = mapped_column(String(20), default="unknown")  # minute|hour|day|unknown
    collection_status: Mapped[str] = mapped_column(String(60), default="imported")
    # Collection provenance is distinct from the source-authored timestamp.
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=True)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=True)
    __table_args__ = (UniqueConstraint("case_id", "source_id", name="uq_post_source"),)


class Comment(Base, TimestampMixin):
    __tablename__ = "comments"
    id: Mapped[str] = uuid_pk()
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    stable_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    post_id: Mapped[str | None] = mapped_column(ForeignKey("posts.id"), nullable=True)
    parent_comment_id: Mapped[str | None] = mapped_column(ForeignKey("comments.id"), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str] = mapped_column(Text, default="")
    author_ref: Mapped[str] = mapped_column(String(255), default="unknown")
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    timestamp_precision: Mapped[str] = mapped_column(String(20), default="unknown")
    permalink: Mapped[str | None] = mapped_column(Text, nullable=True)
    # available|login_required|inaccessible|not_checked|unavailable
    permalink_status: Mapped[str] = mapped_column(String(30), default="not_checked")
    dedup_key: Mapped[str] = mapped_column(String(200), index=True)
    review_status: Mapped[str] = mapped_column(String(40), default="unreviewed")
    uncertain_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)


class MediaAsset(Base, TimestampMixin):
    __tablename__ = "media_assets"
    id: Mapped[str] = uuid_pk()
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    object_key: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    byte_length: Mapped[int] = mapped_column(Integer)
    mime_type: Mapped[str] = mapped_column(String(80))
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    phash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    exif_gps: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON; metadata-reported only
    kind: Mapped[str] = mapped_column(String(30), default="original")  # original|crop|redacted|annotation
    derivative_of_id: Mapped[str | None] = mapped_column(ForeignKey("media_assets.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(500), default="")


class Claim(Base, TimestampMixin):
    __tablename__ = "claims"
    id: Mapped[str] = uuid_pk()
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    post_id: Mapped[str | None] = mapped_column(ForeignKey("posts.id"), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    text_span: Mapped[str] = mapped_column(Text, default="{}")  # JSON [start,end]
    scope: Mapped[str] = mapped_column(String(120), default="")


class EvidenceRecord(Base, TimestampMixin):
    __tablename__ = "evidence_records"
    id: Mapped[str] = uuid_pk()
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    input_id: Mapped[str | None] = mapped_column(ForeignKey("inputs.id"), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    method: Mapped[str] = mapped_column(String(120))
    object_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    snapshot_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_kind: Mapped[str] = mapped_column(String(60))  # import|snapshot|snippet|screenshot|export
    allowed_use: Mapped[str] = mapped_column(Text, default="{}")
    timestamp_provenance: Mapped[str] = mapped_column(Text, default="{}")
    note: Mapped[str] = mapped_column(Text, default="")


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    id: Mapped[str] = uuid_pk()
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    tool: Mapped[str] = mapped_column(String(120))
    model_version: Mapped[str] = mapped_column(String(120), default="")
    parameters: Mapped[str] = mapped_column(Text, default="{}")
    input_evidence_ids: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(30), default="started")
    structured_output: Mapped[str] = mapped_column(Text, default="{}")
    errors: Mapped[str] = mapped_column(Text, default="[]")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Finding(Base, TimestampMixin):
    __tablename__ = "findings"
    id: Mapped[str] = uuid_pk()
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    question: Mapped[str] = mapped_column(Text)
    conclusion_category: Mapped[str] = mapped_column(String(80))
    evidence_ids: Mapped[str] = mapped_column(Text, default="[]")
    excerpts: Mapped[str] = mapped_column(Text, default="[]")
    limitations: Mapped[str] = mapped_column(Text, default="[]")
    contradictions: Mapped[str] = mapped_column(Text, default="[]")
    analysis_run_id: Mapped[str | None] = mapped_column(ForeignKey("analysis_runs.id"), nullable=True)
    review_status: Mapped[str] = mapped_column(String(40), default="unreviewed")
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Alert(Base, TimestampMixin):
    """Materialized review cue with durable analyst workflow state.

    The derived payload can be recomputed; acknowledgement/resolution and its
    audit trail must survive refreshes and process restarts.
    """
    __tablename__ = "alerts"
    __table_args__ = (UniqueConstraint("case_id", "dedup_key", name="uq_alert_case_dedup"),)
    id: Mapped[str] = uuid_pk()
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    dedup_key: Mapped[str] = mapped_column(String(200))
    alert_type: Mapped[str] = mapped_column("type", String(80), index=True)
    title: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(30), index=True)
    status: Mapped[str] = mapped_column(String(30), default="open", index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    attention_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_type: Mapped[str] = mapped_column(String(80), default="not_applicable")
    rule: Mapped[str] = mapped_column(Text, default="")
    narrative_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    evidence_ids: Mapped[str] = mapped_column(Text, default="[]")
    recommended_action: Mapped[str] = mapped_column(Text, default="")
    limitations: Mapped[str] = mapped_column(Text, default="[]")
    payload: Mapped[str] = mapped_column(Text, default="{}")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Place(Base):
    __tablename__ = "places"
    id: Mapped[str] = uuid_pk()
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(300))
    precision: Mapped[str] = mapped_column(String(40))  # country|region|city|landmark|camera_position
    geometry: Mapped[str | None] = mapped_column(Text, nullable=True)  # candidate region, never a fake pin
    role: Mapped[str] = mapped_column(String(40), default="depicted")  # depicted|camera_position|mention


class LocationFinding(Base):
    __tablename__ = "location_findings"
    id: Mapped[str] = uuid_pk()
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    media_asset_id: Mapped[str] = mapped_column(ForeignKey("media_assets.id"))
    place_id: Mapped[str | None] = mapped_column(ForeignKey("places.id"), nullable=True)
    # metadata_reported|visual_candidate|corroborated|conflicting|insufficient
    status: Mapped[str] = mapped_column(String(40))
    evidence_ids: Mapped[str] = mapped_column(Text, default="[]")
    observations: Mapped[str] = mapped_column(Text, default="[]")  # clues kept separate from interpretation
    reviewer_status: Mapped[str] = mapped_column(String(40), default="unreviewed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CoordinationCandidate(Base):
    __tablename__ = "coordination_candidates"
    id: Mapped[str] = uuid_pk()
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    account_ids: Mapped[str] = mapped_column(Text)           # JSON
    date_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    date_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    episodes: Mapped[str] = mapped_column(Text, default="[]")
    features: Mapped[str] = mapped_column(Text, default="{}")
    baseline: Mapped[str] = mapped_column(Text, default="corpus-only baseline")
    alternatives: Mapped[str] = mapped_column(Text, default="[]")
    # review_candidate|insufficient_evidence|reviewed_hypothesis
    review_state: Mapped[str] = mapped_column(String(40), default="review_candidate")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --------------------------------------------------------------------------- graph
class GraphNode(Base, TimestampMixin):
    __tablename__ = "graph_nodes"
    id: Mapped[str] = uuid_pk()
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    label: Mapped[str] = mapped_column(String(500))
    properties: Mapped[str] = mapped_column(Text, default="{}")
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("case_id", "entity_type", "entity_id", name="uq_graph_entity"),)


class GraphEdge(Base, TimestampMixin):
    __tablename__ = "graph_edges"
    id: Mapped[str] = uuid_pk()
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    source_node_id: Mapped[str] = mapped_column(ForeignKey("graph_nodes.id"))
    target_node_id: Mapped[str] = mapped_column(ForeignKey("graph_nodes.id"))
    relationship: Mapped[str] = mapped_column(String(80), index=True)
    # fact|similarity|hypothesis|note  — distinct styles/labels in the UI
    derivation_class: Mapped[str] = mapped_column(String(20), index=True)
    evidence_ids: Mapped[str] = mapped_column(Text, default="[]")
    analysis_run_id: Mapped[str | None] = mapped_column(ForeignKey("analysis_runs.id"), nullable=True)
    time_interval: Mapped[str | None] = mapped_column(Text, nullable=True)
    statement: Mapped[str] = mapped_column(Text, default="")
    idempotency_key: Mapped[str | None] = mapped_column(String(300), nullable=True, index=True)
    __table_args__ = (UniqueConstraint("case_id", "idempotency_key", name="uq_edge_key"),)


# --------------------------------------------------------------------------- jobs / events
class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = uuid_pk()
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(80))
    # queued|running|waiting_for_access|waiting_for_review|completed|failed|cancelled
    lifecycle: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    # complete|partial|insufficient_evidence (null until completed)
    outcome: Mapped[str | None] = mapped_column(String(30), nullable=True)
    stage: Mapped[str] = mapped_column(String(60), default="queued")
    counts: Mapped[str] = mapped_column(Text, default="{}")
    limitations: Mapped[str] = mapped_column(Text, default="[]")
    warnings: Mapped[str] = mapped_column(Text, default="[]")
    parameters: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    client_idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        UniqueConstraint("case_id", "client_idempotency_key", name="uq_job_client_key"),
    )


class JobEvent(Base):
    __tablename__ = "job_events"
    id: Mapped[str] = uuid_pk()
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(60))
    payload: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("job_id", "seq", name="uq_job_event_seq"),)


# --------------------------------------------------------------------------- comments analysis
class CommentAnalysis(Base):
    __tablename__ = "comment_analyses"
    id: Mapped[str] = uuid_pk()
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    comment_id: Mapped[str] = mapped_column(ForeignKey("comments.id"), index=True)
    categories: Mapped[str] = mapped_column(Text, default="[]")
    evidence_spans: Mapped[str] = mapped_column(Text, default="[]")
    explanation: Mapped[str] = mapped_column(Text, default="")
    scores: Mapped[str] = mapped_column(Text, default="{}")
    validation_status: Mapped[str] = mapped_column(String(60), default="heuristic-v1-uncalibrated")
    suggested_action: Mapped[str] = mapped_column(String(120), default="human_review")
    model_version: Mapped[str] = mapped_column(String(120), default="local-rules-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --------------------------------------------------------------------------- OSINT / analytics evidence
class OsintReport(Base):
    """Immutable, source-attributed public-infrastructure investigation report.

    Provider responses are stored as a versioned JSON document so the UI never
    has to substitute synthetic values when a source fails. Each module keeps its
    own outcome, collection time, limitations and source URL.
    """
    __tablename__ = "osint_reports"
    id: Mapped[str] = uuid_pk()
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    target: Mapped[str] = mapped_column(Text)
    target_type: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30))
    report: Mapped[str] = mapped_column(Text, default="{}")
    object_hash: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class GeoObservation(Base):
    """A source-reported location, never an inferred live position.

    Precision and provenance are mandatory because a place-name mention, an
    EXIF point and a visually confirmed landmark answer different questions.
    """
    __tablename__ = "geo_observations"
    id: Mapped[str] = uuid_pk()
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    post_id: Mapped[str | None] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), nullable=True)
    media_asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=True)
    location_name: Mapped[str] = mapped_column(String(300), default="")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    precision: Mapped[str] = mapped_column(String(40), default="unknown")
    source: Mapped[str] = mapped_column(String(60), default="authorized_import")
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MediaForensics(Base):
    """Versioned media-screening output, separate from a deepfake verdict."""
    __tablename__ = "media_forensics"
    id: Mapped[str] = uuid_pk()
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    media_asset_id: Mapped[str] = mapped_column(ForeignKey("media_assets.id", ondelete="CASCADE"), index=True)
    analysis_run_id: Mapped[str | None] = mapped_column(ForeignKey("analysis_runs.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="screened")
    indicators: Mapped[str] = mapped_column(Text, default="{}")
    model_result: Mapped[str] = mapped_column(Text, default="{}")
    limitations: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


# --------------------------------------------------------------------------- exports / audit
class Export(Base):
    __tablename__ = "exports"
    id: Mapped[str] = uuid_pk()
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    scope: Mapped[str] = mapped_column(String(40))   # all|selected|flagged
    redaction_mode: Mapped[str] = mapped_column(String(30))  # redacted|full
    fmt: Mapped[str] = mapped_column(String(20))     # pdf|json|csv|html
    status: Mapped[str] = mapped_column(String(30), default="queued")
    artifact_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    manifest: Mapped[str] = mapped_column(Text, default="{}")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = uuid_pk()
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"),
                                                nullable=True, index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    target_type: Mapped[str] = mapped_column(String(60), default="")
    target_id: Mapped[str] = mapped_column(String(36), default="")
    detail: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
