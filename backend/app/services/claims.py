"""Claim extraction and evidence-backed verification (section 14).

Without a configured fact-check/search provider the workflow still does useful,
honest work: it splits compound text into verifiable propositions with source
spans, matches any *imported* fact-check records, and otherwise produces a
sourced search query plan plus 'insufficient available evidence'. No search
result is never treated as proof of falsity.
"""
from __future__ import annotations

import json
import re
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AnalysisRun, Claim, EvidenceRecord, Post
from ..registry import CLAIM, POST
from . import graph
from .textutil import normalize_text, split_sentences

OPINION_PREFIXES = ("i like", "i love", "i think", "i feel", "mujhe pasand",
                    "mujhe lagta", "meri rai", "in my opinion")
URL_RE = re.compile(r"https?://[^\s]+")


def extract_claims(db: Session, case_id: str, analysis_run: AnalysisRun) -> list[Claim]:
    posts = db.scalars(select(Post).where(Post.case_id == case_id)).all()
    existing = {(c.post_id, c.text) for c in db.scalars(
        select(Claim).where(Claim.case_id == case_id)).all()}
    created: list[Claim] = []
    for post in posts:
        for start, end, sentence in split_sentences(post.raw_text):
            clean = sentence.strip()
            if len(clean.split()) < 5:
                continue
            if (post.id, clean) in existing:
                continue  # idempotent re-runs never duplicate propositions
            lowered = clean.lower()
            scope = "opinion_or_preference" if lowered.startswith(OPINION_PREFIXES) else "factual_proposition"
            claim = Claim(
                case_id=case_id, post_id=post.id, text=clean,
                text_span=json.dumps([start, end]), scope=scope,
            )
            db.add(claim)
            db.flush()
            graph.upsert_node(db, case_id, CLAIM, claim.id, clean[:90], {"scope": scope})
            graph.add_edge(db, case_id, POST, post.id, CLAIM, claim.id, "ASSERTS_CLAIM",
                           statement="Text span in this post states the proposition")
            created.append(claim)
    return created


def build_query_plan(claim: Claim, case_languages: list[str]) -> list[dict]:
    """Dork-style plan (section 25 of the design report). Visible in the UI."""
    text = claim.text
    distinctive = max((s for s in re.split(r"[,.]", text) if len(s.split()) >= 4),
                      key=len, default=text)
    plan = [
        {"purpose": "exact phrase", "query": f'"{distinctive.strip()}"'},
        {"purpose": "site restricted", "query": f'site:instagram.com "{distinctive.strip()[:80]}"'},
        {"purpose": "site restricted", "query": f'site:facebook.com "{distinctive.strip()[:80]}"'},
    ]
    for raw_url in URL_RE.findall(text):
        plan.append({"purpose": "canonical destination check", "query": raw_url})
    if "hi" in case_languages:
        plan.append({"purpose": "romanized spelling variants are searched separately; "
                                "translated hits are never labeled exact wording matches",
                     "query": distinctive.strip()})
    return plan


def match_imported_factchecks(db: Session, case_id: str) -> dict[str, dict]:
    """Fact-check records may be supplied as authorized JSON imports."""
    records = db.scalars(select(EvidenceRecord).where(
        EvidenceRecord.case_id == case_id,
        EvidenceRecord.source_kind == "factcheck_import")).all()
    library: list[dict] = []
    for record in records:
        from . import storage
        try:
            payload = json.loads(storage.get_object(record.snapshot_key).decode("utf-8"))
            library.extend(payload.get("factchecks", []))
        except Exception:
            continue
    matches: dict[str, dict] = {}
    claims = db.scalars(select(Claim).where(Claim.case_id == case_id)).all()
    for claim in claims:
        best, best_ratio, contained = None, 0.0, False
        normalized_claim = normalize_text(claim.text)
        for item in library:
            normalized_fc = normalize_text(item.get("claim", ""))
            ratio = SequenceMatcher(None, normalized_claim, normalized_fc).ratio()
            # Prefixes such as "BREAKING:" must not block a match; a long fact-check
            # statement contained inside the post claim is strong, explainable evidence.
            containment = (len(normalized_fc.split()) >= 8 and normalized_fc in normalized_claim)
            if ratio > best_ratio:
                best, best_ratio, contained = item, ratio, containment
        if best and (best_ratio >= 0.6 or contained):
            matches[claim.id] = {"outcome": best["outcome"], "ratio": round(best_ratio, 3),
                                 "matched_by_containment": contained,
                                 "source": best.get("source"), "checked_at": best.get("checked_at")}
    return matches
