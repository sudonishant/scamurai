"""Readable reports and evidence exports (section 18).

* first page states purpose, scope, window, counts, coverage and review status;
* established findings precede signals, unknowns and conflicting evidence;
* original text and machine interpretation are visually distinct;
* redacted sharing mode vs restricted full-evidence mode;
* every artifact gets a SHA-256 manifest and an expiring download link;
* CSV formula injection and HTML/script injection are neutralized.
"""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import (
    Comment, CommentAnalysis, CoordinationCandidate, Export, Finding,
    MediaAsset, Post, SourceAccess, utcnow,
)
from ..security import csv_safe, mask_identifier, safe_html
from . import storage
from .findings import evidence_quality

settings = get_settings()
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?<!\d)(\+?\d[\d\s\-]{8,}\d)(?!\d)")


def _redact(text: str) -> str:
    text = EMAIL_RE.sub(lambda m: mask_identifier(m.group(0)), text)
    text = PHONE_RE.sub(lambda m: mask_identifier(m.group(0).strip()), text)
    return text


def _bucket(finding: Finding) -> str:
    if finding.review_status == "rejected":
        return "rejected_by_reviewer"
    if json.loads(finding.contradictions or "[]"):
        return "conflicting_evidence"
    category = finding.conclusion_category
    if finding.review_status == "accepted" or category.endswith("exact_file") or \
            category in ("supported", "refuted", "mixed", "out_of_context") or \
            category.endswith("metadata_reported"):
        return "established"
    if "insufficient" in category or "not_fact_checkable" in category:
        return "unknowns"
    return "signals_and_hypotheses"


def _gather(db: Session, case, export: Export) -> dict:
    comments = db.scalars(select(Comment).where(Comment.case_id == case.id)).all()
    analyses = {a.comment_id: a for a in db.scalars(
        select(CommentAnalysis).where(CommentAnalysis.case_id == case.id)).all()}
    findings = db.scalars(select(Finding).where(Finding.case_id == case.id)).all()
    access = db.scalars(select(SourceAccess).where(SourceAccess.case_id == case.id)).all()
    media = db.scalars(select(MediaAsset).where(MediaAsset.case_id == case.id)).all()
    posts = db.scalars(select(Post).where(Post.case_id == case.id)).all()
    candidates = db.scalars(select(CoordinationCandidate).where(
        CoordinationCandidate.case_id == case.id)).all()

    if export.scope == "flagged":
        comments = [c for c in comments if (analyses.get(c.id) and
                    any("insult" in x or "threat" in x or "hate" in x or "harassment" in x
                        for x in json.loads(analyses[c.id].categories)))]
    elif export.scope == "selected" and export.manifest:
        selected = set(json.loads(export.manifest).get("selected_ids", []))
        comments = [c for c in comments if c.id in selected]

    if export.redaction_mode == "redacted":
        for comment in comments:
            comment.raw_text = _redact(comment.raw_text)
            comment.author_ref = mask_identifier(comment.author_ref)

    buckets: dict[str, list[Finding]] = {"established": [], "signals_and_hypotheses": [],
                                         "unknowns": [], "conflicting_evidence": [],
                                         "rejected_by_reviewer": []}
    for finding in findings:
        buckets[_bucket(finding)].append(finding)

    coverage = [json.loads(a.detail) for a in access if a.detail.startswith("{")]
    return {"comments": comments, "analyses": analyses, "buckets": buckets, "coverage": coverage,
            "media": media, "posts": posts, "candidates": candidates,
            "access_outcomes": [a.outcome for a in access]}


def _rubric_for_record(kind: str) -> dict:
    # Written-checklist defaults for imported material; components stay visible.
    checklist = {
        "snapshot": {"D": 0.8, "I": 1.0, "C": 0.7, "T": 0.6, "R": 0.9},
        "screenshot_or_media": {"D": 0.6, "I": 1.0, "C": 0.5, "T": 0.4, "R": 0.8},
    }
    return evidence_quality(checklist.get(kind, {"D": 0.5, "I": 0.8, "C": 0.5, "T": 0.4, "R": 0.6}))


# --------------------------------------------------------------------- JSON / CSV
def _build_json(db: Session, case, export: Export, data: dict) -> bytes:
    payload = {
        "case": {"id": case.id, "title": case.title, "purpose": case.purpose,
                 "languages": json.loads(case.languages), "schema_version": case.schema_version},
        "export": {"scope": export.scope, "redaction_mode": export.redaction_mode,
                   "generated_at": utcnow().isoformat(),
                   "coverage_limitations": data["coverage"],
                   "source_access_outcomes": data["access_outcomes"]},
        "findings": {k: [{"question": f.question, "category": f.conclusion_category,
                          "review_status": f.review_status,
                          "evidence_ids": json.loads(f.evidence_ids),
                          "limitations": json.loads(f.limitations)} for f in v]
                     for k, v in data["buckets"].items()},
        "comments": [{"id": c.id, "text": c.raw_text, "author_ref": c.author_ref,
                      "timestamp": c.timestamp.isoformat() if c.timestamp else None,
                      "precision": c.timestamp_precision, "permalink": c.permalink,
                      "permalink_status": c.permalink_status,
                      "analysis": (json.loads(data["analyses"][c.id].categories)
                                   if c.id in data["analyses"] else None)}
                     for c in data["comments"]],
        "media": [{"id": m.id, "filename": m.filename, "sha256": m.sha256,
                   "byte_length": m.byte_length, "phash": m.phash} for m in data["media"]],
        "evidence_quality_rubric": _rubric_for_record("snapshot"),
        "legal_note": "Hashes and manifests support integrity; they are not court-certified evidence.",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def _build_csv(db: Session, case, export: Export, data: dict) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["evidence_id", "original_text", "author_ref_masked"
                     if export.redaction_mode == "redacted" else "author_ref",
                     "timestamp", "timestamp_precision", "permalink", "permalink_status",
                     "categories", "model_version", "validation_status", "review_status"])
    for comment in data["comments"]:
        analysis = data["analyses"].get(comment.id)
        writer.writerow([
            comment.id, csv_safe(comment.raw_text), csv_safe(comment.author_ref),
            comment.timestamp.isoformat() if comment.timestamp else "",
            comment.timestamp_precision, csv_safe(comment.permalink or "unavailable"),
            comment.permalink_status,
            csv_safe(";".join(json.loads(analysis.categories)) if analysis else ""),
            analysis.model_version if analysis else "",
            analysis.validation_status if analysis else "",
            comment.review_status,
        ])
    return buf.getvalue().encode("utf-8")


# --------------------------------------------------------------------- HTML
def _build_html(db: Session, case, export: Export, data: dict) -> bytes:
    css = """<style>body{font-family:'DejaVu Sans',Arial,sans-serif;margin:32px;color:#1a1a1a}
    h1{font-size:22px}h2{border-bottom:2px solid #444;margin-top:28px}
    .meta{background:#f4f6f8;padding:14px;border-radius:8px}
    .finding{border:1px solid #ccc;border-radius:8px;padding:12px;margin:10px 0}
    .cat{font-weight:bold}.lim{color:#7a5b00;font-size:13px}
    .machine{color:#555;font-style:italic;border-left:3px solid #999;padding-left:8px}
    table{border-collapse:collapse;width:100%;font-size:13px}td,th{border:1px solid #bbb;padding:6px;text-align:left}
    .unknown{background:#fff8e1}.conflict{background:#fdecea}.established{background:#eef7ee}</style>"""
    parts = [f"<!doctype html><html><head><meta charset='utf-8'><title>{safe_html(case.title)}</title>",
             css, "</head><body>"]
    parts.append(f"<h1>{safe_html(case.title)}</h1><div class='meta'>"
                 f"<b>Purpose:</b> {safe_html(case.purpose)}<br>"
                 f"<b>Scope:</b> {export.scope} | <b>Mode:</b> {export.redaction_mode}<br>"
                 f"<b>Generated:</b> {utcnow().isoformat()}<br>"
                 f"<b>Source access outcomes:</b> {safe_html(', '.join(data['access_outcomes']) or 'none')}<br>"
                 f"<b>Coverage:</b> {safe_html(json.dumps(data['coverage'], ensure_ascii=False))}<br>"
                 f"<b>Legal note:</b> Hashes support integrity; this is not certified evidence.</div>")
    titles = {"established": "1 — Established (evidence-backed)",
              "signals_and_hypotheses": "2 — Signals and hypotheses",
              "unknowns": "3 — What remains unknown / insufficient",
              "conflicting_evidence": "4 — Conflicting evidence",
              "rejected_by_reviewer": "5 — Rejected by reviewer"}
    for key, title in titles.items():
        items = data["buckets"][key]
        if not items:
            continue
        parts.append(f"<h2>{safe_html(title)} ({len(items)})</h2>")
        for f in items:
            parts.append(
                f"<div class='finding {key}'><div class='cat'>{safe_html(f.conclusion_category)}</div>"
                f"<div>{safe_html(f.question)}</div>"
                f"<div class='machine'>Machine interpretation · evidence {safe_html(','.join(json.loads(f.evidence_ids)))}</div>"
                f"<div class='lim'>Limitations: {safe_html(' | '.join(json.loads(f.limitations)))}</div>"
                f"<div>Review: {safe_html(f.review_status)}</div></div>")
    parts.append("<h2>Comments</h2><table><tr><th>ID</th><th>Original text</th><th>Author</th>"
                 "<th>Time</th><th>Link</th><th>Analysis</th></tr>")
    for c in data["comments"]:
        analysis = data["analyses"].get(c.id)
        parts.append("<tr>" + "".join(f"<td>{safe_html(v)}</td>" for v in [
            c.id[:8], c.raw_text, c.author_ref,
            c.timestamp.isoformat() if c.timestamp else "precision: " + c.timestamp_precision,
            c.permalink or f"unavailable ({c.permalink_status})",
            ";".join(json.loads(analysis.categories)) if analysis else "not analyzed"]) + "</tr>")
    parts.append("</table></body></html>")
    return "".join(parts).encode("utf-8")


# --------------------------------------------------------------------- PDF
def _build_pdf(db: Session, case, export: Export, data: dict) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate, Spacer)
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_name = "Helvetica"
    for candidate in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",):
        if Path(candidate).exists():
            pdfmetrics.registerFont(TTFont("DejaVu", candidate))
            font_name = "DejaVu"
            break
    styles = getSampleStyleSheet()
    base = ParagraphStyle("base", parent=styles["Normal"], fontName=font_name, fontSize=9, leading=13)
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontName=font_name)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontName=font_name)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title=case.title)
    story = [Paragraph(safe_html(case.title), h1), Spacer(1, 0.3 * cm),
             Paragraph(f"Purpose: {safe_html(case.purpose)}", base),
             Paragraph(f"Scope: {export.scope} · Mode: {export.redaction_mode} · "
                       f"Generated: {utcnow().isoformat()}", base),
             Paragraph(f"Source access: {safe_html(', '.join(data['access_outcomes']) or 'none')}", base),
             Paragraph("Hashes/manifests support integrity; this report is not court-certified evidence.", base),
             Spacer(1, 0.4 * cm)]
    for key, title in [("established", "Established"), ("signals_and_hypotheses", "Signals and hypotheses"),
                       ("unknowns", "Unknowns / insufficient"), ("conflicting_evidence", "Conflicting"),
                       ("rejected_by_reviewer", "Rejected by reviewer")]:
        items = data["buckets"][key]
        if not items:
            continue
        story.append(Paragraph(f"{title} ({len(items)})", h2))
        for f in items:
            story.append(Paragraph(f"<b>{safe_html(f.conclusion_category)}</b> — {safe_html(f.question)}", base))
            story.append(Paragraph("Limitations: " + safe_html(" | ".join(json.loads(f.limitations))), base))
            story.append(Spacer(1, 0.15 * cm))
    story.append(PageBreak())
    story.append(Paragraph("Comment records (original text distinct from machine interpretation)", h2))
    for c in data["comments"]:
        analysis = data["analyses"].get(c.id)
        story.append(Paragraph(
            f"[{c.id[:8]}] {safe_html(c.raw_text)} — {safe_html(c.author_ref)} · "
            f"{c.timestamp.isoformat() if c.timestamp else 'precision: ' + c.timestamp_precision}", base))
        if analysis:
            story.append(Paragraph(
                f"<i>Machine interpretation: {safe_html(';'.join(json.loads(analysis.categories)))} "
                f"({analysis.model_version}, {analysis.validation_status})</i>", base))
        story.append(Paragraph(
            f"Link: {safe_html(c.permalink or 'unavailable — ' + c.permalink_status)}", base))
        story.append(Spacer(1, 0.12 * cm))
    story.append(PageBreak())
    rubric = _rubric_for_record("snapshot")
    story.append(Paragraph("Manifest & evidence quality", h2))
    story.append(Paragraph(safe_html(json.dumps(rubric, ensure_ascii=False)), base))
    doc.build(story)
    return buf.getvalue()


_BUILDERS = {"json": _build_json, "csv": _build_csv, "html": _build_html, "pdf": _build_pdf}


def run_export(db: Session, case, export: Export) -> Export:
    data = _gather(db, case, export)
    blob = _BUILDERS[export.fmt](db, case, export, data)
    key = storage.put_object(case.id, f"exports/{export.id}.{export.fmt}", blob)
    export.artifact_key = key
    export.sha256 = storage.sha256_hex(blob)
    export.status = "completed"
    export.expires_at = utcnow() + timedelta(seconds=settings.export_link_ttl_seconds)
    export.manifest = json.dumps({
        "artifact": key, "sha256": export.sha256, "bytes": len(blob),
        "generated_at": utcnow().isoformat(), "scope": export.scope,
        "redaction_mode": export.redaction_mode,
        "selected_ids": json.loads(export.manifest).get("selected_ids", []) if export.manifest else [],
    })
    db.flush()
    return export
