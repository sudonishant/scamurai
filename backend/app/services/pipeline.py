"""Bounded analysis workflows executed by the job runner.

Every task uses the JobContext's single session, writes an AnalysisRun with
tool/version/parameters, checkpoints for cancellation/deadline, records honest
limitations, and returns lifecycle counts. Failures of one source never
collapse into 'nothing exists' — they remain visible in the coverage statement.
"""
from __future__ import annotations

import io
import json

from PIL import Image
from sqlalchemy import select

from ..models import (
    AnalysisRun, Case, Comment, CoordinationCandidate, EvidenceRecord,
    Input, MediaAsset, SourceAccess, utcnow,
)
from ..registry import MEDIA
from . import claims as claims_svc
from . import comments as comments_svc
from . import connectors, coordination, images, location
from . import storage, graph
from .jobs import JobContext
from .findings import create_finding

TOOL_VERSION = "ps03-local-v0.1"


def _analysis_run(ctx: JobContext, tool: str, parameters: dict,
                  evidence_ids: list[str] | None = None) -> AnalysisRun:
    run = AnalysisRun(
        case_id=ctx.case_id, tool=tool, model_version=TOOL_VERSION,
        parameters=json.dumps(parameters), input_evidence_ids=json.dumps(evidence_ids or []),
    )
    ctx.db.add(run)
    ctx.db.flush()
    return run


# --------------------------------------------------------------------- 1. imports / URLs
def import_pipeline(ctx: JobContext) -> dict:
    db = ctx.db
    inputs = db.scalars(select(Input).where(Input.case_id == ctx.case_id)).all()
    run = _analysis_run(ctx, "import_pipeline", {"inputs": len(inputs)})
    limitations: list[str] = []
    fetched = 0
    for inp in inputs:
        ctx.checkpoint()
        if inp.kind != "url":
            continue
        payload = json.loads(inp.payload)
        url = payload.get("url", "")
        ctx.stage(f"fetching {url[:60]}")
        result = connectors.fetch_permitted_source(url)
        db.add(SourceAccess(
            case_id=ctx.case_id, input_id=inp.id, provider=result.provider,
            method="public_page_fetch", capability="fetch_post",
            outcome=result.outcome, detail=result.detail))
        if result.outcome == "successful":
            raw = result.text.encode("utf-8")
            key = storage.put_object(ctx.case_id, f"snapshots/{inp.id}.html", raw)
            evidence = EvidenceRecord(
                case_id=ctx.case_id, input_id=inp.id, source_url=result.final_url or url,
                method="public_page_fetch", object_hash=storage.sha256_hex(raw),
                snapshot_key=key, source_kind="snapshot",
                note="Search-index leads must be opened before becoming confirmed sources")
            db.add(evidence)
            db.flush()
            graph.evidence_node(db, evidence)
            fetched += 1
        else:
            limitations.append(f"{url}: {result.outcome} — {result.detail}")
            inp.status = result.outcome
    run.status = "completed"
    run.ended_at = utcnow()
    return {"counts": {"sources_fetched": fetched},
            "limitations": limitations,
            "outcome": "partial" if limitations else "complete"}


# --------------------------------------------------------------------- 2. image matching
def image_matching(ctx: JobContext) -> dict:
    db = ctx.db
    assets = db.scalars(select(MediaAsset).where(
        MediaAsset.case_id == ctx.case_id, MediaAsset.kind == "original")).all()
    run = _analysis_run(ctx, "staged_image_pipeline",
                        {"phash_threshold": images.settings.phash_distance_threshold})
    ctx.stage("comparing media corpus")
    comparisons, similarity_edges = 0, 0
    for i, a in enumerate(assets):
        for b in assets[i + 1:]:
            ctx.checkpoint()
            comparisons += 1
            exact = a.sha256 == b.sha256 and a.byte_length == b.byte_length
            img_a = Image.open(io.BytesIO(storage.get_object(a.object_key)))
            img_b = Image.open(io.BytesIO(storage.get_object(b.object_key)))
            result = images.compare_pair(img_a, img_b, a.phash, b.phash, exact)
            run.structured_output = json.dumps({"last_comparison": result})
            if result["match_type"] in ("likely_same_visual_source", "partial_region_match"):
                edge = graph.add_edge(
                    db, ctx.case_id, MEDIA, a.id, MEDIA, b.id, "VISUAL_SOURCE_MATCH",
                    analysis_run_id=run.id,
                    statement=f"{result['match_type']} via {result['method']}",
                    evidence_ids=[a.id, b.id])
                if edge:
                    similarity_edges += 1
            create_finding(
                db, ctx.case_id,
                question=f"Do {a.filename} and {b.filename} share image content?",
                conclusion_category=f"image_match:{result['match_type']}",
                evidence_ids=[a.id, b.id],
                excerpts=[f"SHA-256 {a.sha256[:12]} vs {b.sha256[:12]}",
                          f"byte length {a.byte_length} vs {b.byte_length} (size alone is never a match)"],
                limitations=[result["limitation"],
                             "File identity does not establish first uploader or caption truth."],
                analysis_run=run)
    run.status = "completed"
    run.ended_at = utcnow()
    return {"counts": {"comparisons": comparisons, "similarity_edges": similarity_edges},
            "outcome": "complete"}


# --------------------------------------------------------------------- 3. comments
def comment_analysis(ctx: JobContext) -> dict:
    db = ctx.db
    comments = db.scalars(select(Comment).where(Comment.case_id == ctx.case_id)).all()
    run = _analysis_run(ctx, "comment_multilabel_rules", {"count": len(comments)})
    ctx.stage("analyzing comments")
    categories: dict[str, int] = {}
    for comment in comments:
        ctx.checkpoint()
        record = comments_svc.analyze_and_store(db, ctx.case_id, comment.id)
        for category in json.loads(record.categories):
            categories[category] = categories.get(category, 0) + 1
    run.status = "completed"
    run.ended_at = utcnow()
    return {"counts": {"comments_analyzed": len(comments), **categories}, "outcome": "complete"}


# --------------------------------------------------------------------- 4. coordination
def coordination_detection(ctx: JobContext) -> dict:
    db = ctx.db
    run = _analysis_run(ctx, "coordination_features",
                        {"window_minutes": images.settings.coordination_window_minutes})
    ctx.stage("extracting repeated-alignment features")
    summary = coordination.detect(db, ctx.case_id)
    candidates = db.scalars(select(CoordinationCandidate).where(
        CoordinationCandidate.case_id == ctx.case_id)).all()
    for candidate in candidates:
        # Evidence IDs must resolve to graph entities (the accounts); the
        # synthetic episode keys stay in the excerpts, never presented as IDs.
        account_ids = json.loads(candidate.account_ids)
        create_finding(
            db, ctx.case_id,
            question="Is repeated, unusually aligned behavior observable between these accounts?",
            conclusion_category=f"coordination:{candidate.review_state}",
            evidence_ids=account_ids,
            excerpts=[f"Episodes (event lineage): {candidate.episodes}",
                      f"Feature values: {candidate.features}"],
            limitations=[
                "Alignment of activity is not proof of shared ownership or deceptive intent.",
                "Corpus-only baseline; platform-wide behavior is not observable.",
                *json.loads(candidate.alternatives),
            ],
            analysis_run=run)
    run.status = "completed"
    run.structured_output = json.dumps(summary)
    run.ended_at = utcnow()
    return {"counts": summary, "outcome": "complete",
            "limitations": ["A detected community is not evidence of wrongdoing."]}


# --------------------------------------------------------------------- 5. claims
def claim_workflow(ctx: JobContext) -> dict:
    db = ctx.db
    case = db.get(Case, ctx.case_id)
    run = _analysis_run(ctx, "claim_extraction_and_verification", {})
    ctx.stage("extracting verifiable propositions")
    created = claims_svc.extract_claims(db, ctx.case_id, run)
    factchecks = claims_svc.match_imported_factchecks(db, ctx.case_id)
    languages = json.loads(case.languages)
    insufficient = 0
    for claim in created:
        ctx.checkpoint()
        if claim.scope == "opinion_or_preference":
            category = "not_fact_checkable"
            limitations = ["Opinion/preference is not a verifiable factual claim."]
            evidence: list[str] = []
        elif claim.id in factchecks:
            match = factchecks[claim.id]
            category = match["outcome"]
            limitations = [f"Matched imported fact-check (similarity {match['ratio']}); "
                           f"verify it addresses the same event: {match['source']}"]
            ev = db.scalar(select(EvidenceRecord).where(
                EvidenceRecord.case_id == ctx.case_id,
                EvidenceRecord.source_kind == "factcheck_import"))
            evidence = [ev.id] if ev else []
        else:
            category = "insufficient_available_evidence"
            insufficient += 1
            plan = claims_svc.build_query_plan(claim, languages)
            run.structured_output = json.dumps({"query_plan": plan}, ensure_ascii=False)
            limitations = [
                "No search result is not proof of falsity.",
                "Approved query plan prepared; external search is a separate, policy-checked step.",
                json.dumps(plan, ensure_ascii=False),
            ]
            evidence = [claim.post_id] if claim.post_id else []
        create_finding(
            db, ctx.case_id,
            question=f"Is this claim supported? — {claim.text[:120]}",
            conclusion_category=category, evidence_ids=evidence,
            excerpts=[claim.text], limitations=limitations, analysis_run=run)
    run.status = "completed"
    run.ended_at = utcnow()
    return {"counts": {"claims": len(created), "insufficient": insufficient},
            "outcome": "partial" if insufficient else "complete"}


# --------------------------------------------------------------------- 6. location
def location_analysis(ctx: JobContext) -> dict:
    db = ctx.db
    assets = db.scalars(select(MediaAsset).where(
        MediaAsset.case_id == ctx.case_id, MediaAsset.kind == "original")).all()
    run = _analysis_run(ctx, "photo_to_location", {})
    statuses: dict[str, int] = {}
    for asset in assets:
        ctx.checkpoint()
        ctx.stage(f"location clues for {asset.filename}")
        finding = location.analyze_media(db, ctx.case_id, asset, run)
        statuses[finding.status] = statuses.get(finding.status, 0) + 1
        create_finding(
            db, ctx.case_id,
            question=f"Where might {asset.filename} have been captured or what does it depict?",
            conclusion_category=f"location:{finding.status}",
            evidence_ids=json.loads(finding.evidence_ids),
            excerpts=json.loads(finding.observations),
            limitations=[
                "Estimates depict place or camera position at the narrowest supported precision.",
                "A candidate region is not a calibrated error boundary; no live tracking.",
            ],
            analysis_run=run)
    run.status = "completed"
    run.ended_at = utcnow()
    return {"counts": statuses, "outcome": "complete"}


WORKFLOWS = {
    "import_pipeline": import_pipeline,
    "image_matching": image_matching,
    "comment_analysis": comment_analysis,
    "coordination_detection": coordination_detection,
    "claim_workflow": claim_workflow,
    "location_analysis": location_analysis,
}
