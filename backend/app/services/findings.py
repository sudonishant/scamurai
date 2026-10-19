"""Finding creation and the evidence-quality rubric (sections 14-15)."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from ..models import AnalysisRun, Finding


def create_finding(
    db: Session, case_id: str, question: str, conclusion_category: str,
    evidence_ids: list[str], excerpts: list, limitations: list,
    contradictions: list | None = None, analysis_run: AnalysisRun | None = None,
) -> Finding:
    finding = Finding(
        case_id=case_id, question=question, conclusion_category=conclusion_category,
        evidence_ids=json.dumps(evidence_ids), excerpts=json.dumps(excerpts, ensure_ascii=False),
        limitations=json.dumps(limitations), contradictions=json.dumps(contradictions or []),
        analysis_run_id=analysis_run.id if analysis_run else None,
    )
    db.add(finding)
    db.flush()
    return finding


def evidence_quality(checklist: dict[str, float]) -> dict:
    """Q = 30D + 25I + 20C + 15T + 10R.

    Each component is the normalized result of a written checklist (0..1).
    Unknown components produce 'assessment incomplete' instead of silent
    reweighting. Q scores an evidence *record*, never truth or person guilt.
    """
    weights = {"D": 30, "I": 25, "C": 20, "T": 15, "R": 10}
    names = {
        "D": "source directness", "I": "preserved-record integrity",
        "C": "contextual completeness", "T": "timestamp usefulness",
        "R": "reproducibility",
    }
    missing = [k for k in weights if k not in checklist]
    if missing:
        return {
            "status": "assessment_incomplete",
            "missing_components": [f"{k} ({names[k]})" for k in missing],
            "available": {k: checklist[k] for k in checklist if k in weights},
        }
    score = sum(weights[k] * checklist[k] for k in weights)
    return {
        "status": "scored", "quality_score": round(score, 1),
        "rubric": "Q = 30D + 25I + 20C + 15T + 10R (design proposal, not a validated law)",
        "components": {names[k]: checklist[k] for k in weights},
        "scope_note": "Quality of the evidence record only — not truth, credibility of a person, or guilt.",
    }
