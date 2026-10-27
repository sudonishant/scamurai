"""Authorized import-first ingestion (master prompt sections 5-6, 8, 12).

Everything works offline from user-supplied files; live connectors only add
capabilities later. Raw bytes/snapshots are preserved before any normalized
record is created, and every created node/edge is traceable to an input.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    Account,
    Comment,
    EvidenceRecord,
    GeoObservation,
    MediaAsset,
    Post,
    SourceAccess,
    utcnow,
)
from ..registry import (
    ACCOUNT,
    COMMENT,
    EVIDENCE,
    MEDIA,
    POST,
)
from ..security import sanitize_upload_filename, validate_image_signature
from . import graph, images, storage
from .textutil import normalize_text


def _parse_ts(value: str | None, precision: str | None) -> tuple[datetime | None, str]:
    if not value:
        return None, precision or "unknown"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt, precision or ("day" if len(value) <= 10 else "minute")
    except (ValueError, AttributeError):
        return None, "unknown"


def _snapshot(db: Session, case_id: str, input_id: str, raw: bytes, kind: str,
              source_url: str | None = None) -> EvidenceRecord:
    key = storage.put_object(case_id, f"snapshots/{hashlib.sha256(raw).hexdigest()[:16]}-{kind}", raw)
    record = EvidenceRecord(
        case_id=case_id, input_id=input_id, source_url=source_url,
        method="authorized_import", object_hash=hashlib.sha256(raw).hexdigest(),
        snapshot_key=key, source_kind=kind,
        timestamp_provenance=json.dumps({"collected_at": utcnow().isoformat(),
                                         "source_clock": "as provided by exporter"}),
    )
    db.add(record)
    db.flush()
    graph.evidence_node(db, record)
    return record


# --------------------------------------------------------------------------- accounts/posts
def _get_or_create_account(db: Session, case_id: str, platform: str, data: dict) -> Account:
    platform_id = data.get("platform_id")
    account = None
    if platform_id:
        account = db.scalar(select(Account).where(
            Account.case_id == case_id, Account.platform == platform,
            Account.platform_id == platform_id))
    if account is None:
        account = db.scalar(select(Account).where(
            Account.case_id == case_id, Account.platform == platform,
            Account.handle == data["handle"]))
    if account:
        return account
    account = Account(
        case_id=case_id, platform=platform, platform_id=platform_id,
        handle=data["handle"], display_name=data.get("display_name", ""),
        canonical_profile_url=data.get("profile_url"),
        identity_confirmed=bool(data.get("identity_confirmed", False)),
        observed_handles=json.dumps([data["handle"]]),
    )
    db.add(account)
    db.flush()
    graph.upsert_node(db, case_id, ACCOUNT, account.id,
                      f"@{account.handle} ({platform})",
                      {"handle": account.handle, "identity_confirmed": account.identity_confirmed})
    return account


def import_posts_bundle(db: Session, case_id: str, actor_id: str, payload: dict,
                        input_id: str) -> dict:
    platform = payload.get("platform", "unknown-platform")
    accounts = {a["handle"]: _get_or_create_account(db, case_id, platform, a)
                for a in payload.get("accounts", [])}

    # Explicit public cross-links are source-supported facts (still source-attributed).
    for a in payload.get("accounts", []):
        owner = accounts[a["handle"]]
        for other_handle in a.get("public_crosslinks", []):
            if other_handle in accounts:
                graph.add_edge(db, case_id, ACCOUNT, owner.id, ACCOUNT,
                               accounts[other_handle].id, "PUBLICLY_CROSSLINKS",
                               statement=f"Public profile links to @{other_handle}")

    counts = {"accounts": len(accounts), "posts": 0, "media_links": 0, "geo_observations": 0}
    for row in payload.get("posts", []):
        existing = db.scalar(select(Post).where(
            Post.case_id == case_id, Post.source_id == row["source_id"]))
        if existing:
            # Duplicate-safe re-import still records the latest collection
            # contact without moving the original first-seen timestamp.
            existing.collected_at = utcnow()
            if existing.first_seen_at is None:
                existing.first_seen_at = existing.created_at
            continue
        ts, precision = _parse_ts(row.get("timestamp"), row.get("timestamp_precision"))
        account = accounts.get(row.get("account_handle"))
        post = Post(
            case_id=case_id, source_id=row["source_id"], canonical_url=row.get("url"),
            account_id=account.id if account else None, raw_text=row.get("text", ""),
            normalized_text=normalize_text(row.get("text", "")),
            language=row.get("language", "und"), timestamp=ts, timestamp_precision=precision,
            collection_status=row.get("collection_status", "imported"),
        )
        db.add(post)
        db.flush()
        counts["posts"] += 1
        graph.upsert_node(db, case_id, POST, post.id,
                          (post.raw_text[:80] or post.source_id),
                          {"source_id": post.source_id, "url": post.canonical_url})
        if account:
            graph.add_edge(db, case_id, ACCOUNT, account.id, POST, post.id, "PUBLISHED",
                           statement=f"@{account.handle} visible publisher of {post.source_id}")
        for filename in row.get("media", []):
            media = db.scalar(select(MediaAsset).where(
                MediaAsset.case_id == case_id, MediaAsset.filename == filename))
            if media:
                graph.add_edge(db, case_id, POST, post.id, MEDIA, media.id, "CONTAINS_MEDIA")
                counts["media_links"] += 1

        # Optional source-reported location from an authorized export. It is
        # never resolved to a person/device or promoted to verified ground truth.
        location = row.get("location") if isinstance(row.get("location"), dict) else {}
        location_name = str(location.get("name") or row.get("location_name") or "")[:300]
        lat_value = location.get("latitude", row.get("latitude"))
        lon_value = location.get("longitude", row.get("longitude"))
        latitude = longitude = None
        try:
            if lat_value is not None and lon_value is not None:
                latitude, longitude = float(lat_value), float(lon_value)
                if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                    latitude = longitude = None
        except (TypeError, ValueError):
            latitude = longitude = None
        if location_name or (latitude is not None and longitude is not None):
            db.add(GeoObservation(
                case_id=case_id, post_id=post.id, location_name=location_name,
                latitude=latitude, longitude=longitude,
                precision=str(location.get("precision") or row.get("location_precision")
                             or ("reported_point" if latitude is not None else "place_name"))[:40],
                source="post_import_reported", observed_at=ts,
            ))
            counts["geo_observations"] += 1

    db.add(SourceAccess(case_id=case_id, input_id=input_id, provider=platform,
                        method="authorized_import",
                        capability="posts:read", outcome="successful",
                        detail=f"Imported {counts['posts']} posts from user-supplied bundle"))
    return counts



# --------------------------------------------------------------------------- comments
def import_comment_rows(db: Session, case_id: str, actor_id: str, rows: list[dict],
                        meta: dict, input_id: str) -> dict:
    post_by_source: dict[str, Post] = {
        p.source_id: p for p in db.scalars(select(Post).where(Post.case_id == case_id)).all()
        if p.source_id
    }
    post_by_url: dict[str, Post] = {
        p.canonical_url: p for p in post_by_source.values() if p.canonical_url
    }
    created = 0
    uncertain = 0
    for row in rows:
        stable_id = row.get("comment_id") or row.get("stable_id")
        if stable_id and db.scalar(select(Comment).where(
                Comment.case_id == case_id, Comment.stable_id == stable_id)):
            continue
        text = row.get("text", "")
        ts, precision = _parse_ts(row.get("timestamp"), row.get("timestamp_precision"))
        post = post_by_source.get(row.get("post_source_id", "")) or post_by_url.get(row.get("post_url", ""))
        author = row.get("author", "unknown")
        composite = hashlib.sha256(
            json.dumps([normalize_text(text), author, row.get("parent_id"), row.get("timestamp")],
                       ensure_ascii=False).encode("utf-8")).hexdigest()
        is_uncertain = stable_id is None
        if is_uncertain and db.scalar(select(Comment).where(
                Comment.case_id == case_id, Comment.dedup_key == composite)):
            uncertain += 1
            continue  # two people can write "Very good"; only exact composite repeats collapse
        permalink = row.get("permalink") or None
        comment = Comment(
            case_id=case_id, stable_id=stable_id,
            post_id=post.id if post else None,
            raw_text=text, normalized_text=normalize_text(text),
            author_ref=author, timestamp=ts, timestamp_precision=precision,
            permalink=permalink,
            permalink_status=row.get("permalink_status", "available" if permalink else "unavailable"),
            dedup_key=stable_id or composite, uncertain_duplicate=is_uncertain,
        )
        db.add(comment)
        db.flush()
        created += 1
        graph.upsert_node(db, case_id, COMMENT, comment.id, f"{author}: {text[:60]}",
                          {"author_ref": author, "precision": precision})
        if post:
            graph.add_edge(db, case_id, COMMENT, comment.id, POST, post.id, "REPLIES_TO",
                           statement="Comment on post per import record")

    displayed = meta.get("platform_displayed_count")
    comparable = bool(meta.get("counts_comparable"))
    if displayed is not None and comparable:
        coverage = {
            "unique_collected": created,
            "platform_displayed": displayed,
            "coverage_percent": round(100 * created / displayed, 1) if displayed else None,
            "status": "partial" if created < displayed else "complete",
        }
    else:
        coverage = {
            "unique_collected": created,
            "platform_displayed": displayed,
            "coverage_percent": None,
            "status": "partial_list_denominator_not_comparable_or_unknown",
        }
    db.add(SourceAccess(
        case_id=case_id, input_id=input_id, provider=meta.get("platform", "manual-import"),
        method="authorized_import", capability="comments:read",
        outcome="successful", detail=json.dumps(coverage)))
    return {"comments_created": created, "uncertain_duplicates_held": uncertain, "coverage": coverage}


# --------------------------------------------------------------------------- media
def register_media(db: Session, case_id: str, actor_id: str, data: bytes, filename: str,
                   declared_mime: str | None, input_id: str) -> MediaAsset:
    filename = sanitize_upload_filename(filename)
    mime = validate_image_signature(data)  # signature, not extension
    info = images.inspect_image(data, mime)
    digest = storage.sha256_hex(data)
    key = storage.put_object(case_id, f"media/{digest}/{filename}", data)
    snapshot = _snapshot(db, case_id, input_id, data, "screenshot_or_media",
                         source_url=None)
    # Each upload is its own evidence record; byte-identical uploads are linked
    # by an EXACT_FILE_MATCH edge instead of being silently merged.
    asset = MediaAsset(
        case_id=case_id, object_key=key, sha256=digest, byte_length=len(data),
        mime_type=mime, width=info.width, height=info.height, phash=info.phash,
        exif_gps=json.dumps(info.exif_gps) if info.exif_gps else None,
        kind="original", filename=filename,
    )
    db.add(asset)
    db.flush()
    graph.upsert_node(db, case_id, MEDIA, asset.id, filename,
                      {"sha256": digest[:12], "width": info.width, "height": info.height,
                       "byte_length": len(data)})
    graph.add_edge(db, case_id, MEDIA, asset.id, EVIDENCE, snapshot.id, "PRESERVED_AS",
                   statement="Original bytes preserved as an evidence snapshot")
    _wire_exact_matches(db, case_id, asset)
    return asset


def _wire_exact_matches(db: Session, case_id: str, asset: MediaAsset) -> None:
    others = db.scalars(select(MediaAsset).where(
        MediaAsset.case_id == case_id,
        MediaAsset.sha256 == asset.sha256,
        MediaAsset.id != asset.id)).all()
    for other in others:
        graph.add_edge(db, case_id, MEDIA, asset.id, MEDIA, other.id, "EXACT_FILE_MATCH",
                       evidence_ids=[], statement="Identical SHA-256 and byte length")


def parse_csv(raw: bytes) -> list[dict]:
    text = raw.decode("utf-8-sig", errors="replace")
    return list(csv.DictReader(io.StringIO(text)))


def parse_json(raw: bytes) -> dict | list:
    return json.loads(raw.decode("utf-8-sig"))
