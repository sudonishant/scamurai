"""Multilabel comment analysis (master prompt section 12).

Local, deterministic, *uncalibrated* rule layer for Hindi, English and
romanized Hinglish. It is deliberately honest about its limits:

* no single severity score — categories stay separate and abstention is valid;
* quotation, sarcasm and negation are handled conservatively;
* every label carries an evidence span in the original (untranslated) text;
* output is scoped to one comment and can never become a person-level score;
* instruction-like text inside content is flagged as data, never executed.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Comment, CommentAnalysis

LEXICON: dict[str, list[str]] = {
    "threat_like": [
        "maar dunga", "jaan se", "goli", "chaku", "kill you", "behead",
        "harm you", "dekh lenge", "anjaam bura",
    ],
    "targeted_insult": [
        "bewakoof", "buddhu", "gawar", "nalayak", "chamcha", "bekaar",
        "idiot", "stupid", "loser", "dumb", "moron",
    ],
    "harassment": [
        "harass", "stalk", "baar baar pareshan", "shame on you",
        "boycott", "tera picha", "troll",
    ],
    "identity_hate": [
        "anti-national", "go back to your country", "terrorist sympathizer",
        "jati ka", "dharm ke naam pe",
    ],
    "sexual_harassment": [
        "gandi nazar", "badtameezi", "creep", "sexual", "chedna",
    ],
    "spam": [
        "free gift", "click link", "dm me", "winner", "lottery",
        "paise kamao", "buy now", "subscribe my channel", "guaranteed returns",
    ],
}
CRITICISM_MARKERS = [
    "product kharab", "service slow", "paisa wapas", "refund", "not worth",
    "disappointed", "quality achhi nahi", "delivery late", "worst experience",
    "customer care",
]
QUOTATION_MARKERS = ('"', "“", "‘", "unaunhone kaha", "usne kaha", "i condemn",
                     "quote", "yeh shabd", "reported speech")
SARCASM_MARKERS = ("wah!", "great!", "bahut badhiya", "kya baat hai", "sure,")
OPINION_MARKERS = ("i like", "i think", "mujhe lagta", "meri rai", "in my opinion")
INJECTION_PATTERNS = re.compile(
    r"(ignore (all|the|previous) (previous )?instructions|forget your instructions|"
    r"system prompt|send (the )?(secret|api key|password|token)|act as|you are now)",
    re.IGNORECASE,
)
NEGATIONS = ("not", "nahi", "nahin", "mat", "no ", "never")


@dataclass
class CommentResult:
    categories: list[str] = field(default_factory=list)
    spans: list[dict] = field(default_factory=list)
    explanation: str = ""
    scores: dict = field(default_factory=dict)
    suggested_action: str = "human_review"
    validation_status: str = "heuristic-v1-uncalibrated"


def _find_span(text: str, term: str) -> dict | None:
    idx = text.lower().find(term.lower())
    if idx < 0:
        return None
    return {"start": idx, "end": idx + len(term), "term": term}


def _is_negated(text: str, idx: int) -> bool:
    # Only an immediate, close negation counts — otherwise unrelated earlier
    # words ("baat nahi mani to dekh lenge") would suppress real signals.
    prefix = text[max(0, idx - 12):idx].lower()
    return any(neg in prefix for neg in NEGATIONS)


def analyze_comment_text(text: str, parent_context: str = "") -> CommentResult:
    result = CommentResult()
    lowered = text.lower()

    injection = INJECTION_PATTERNS.search(text)
    if injection:
        result.categories.append("prompt_instruction_in_content")
        result.spans.append({"start": injection.start(), "end": injection.end(),
                             "term": injection.group(0)})
        result.explanation = (
            "Instruction-like content detected inside analyzed material. It is treated as "
            "untrusted data and never executed (prompt-injection defense).")
        result.scores["prompt_instruction_in_content"] = 1
        result.suggested_action = "human_review"
        return result

    quoted = any(marker in lowered for marker in QUOTATION_MARKERS) or text.strip().startswith(('"', "“"))

    for category, terms in LEXICON.items():
        hits=0
        for term in terms:
            span = _find_span(text, term)
            if span is None:
                continue
            # Safety-sensitive categories are never silently suppressed by an
            # ambiguous negation; a human reviewer makes the final call.
            if _is_negated(text, span["start"]) and category not in {
                    "threat_like", "identity_hate", "sexual_harassment"}:
                continue
            # Quoted abuse used to condemn it is labeled distinctly, not as the speaker's own.
            if quoted and category in {"targeted_insult", "identity_hate", "sexual_harassment"}:
                result.categories.append(f"quoted_{category}")
            else:
                result.categories.append(category)
            result.spans.append(span)
            hits += 1
        if hits:
            result.scores[category] = hits

    if any(m in lowered for m in CRITICISM_MARKERS) and not result.categories:
        result.categories.append("ordinary_criticism")
        result.scores["ordinary_criticism"] = 1
        result.suggested_action = "no_action"

    if any(m in lowered for m in SARCASM_MARKERS) and not result.categories:
        result.categories.append("uncertain_context_needed")
        result.explanation = "Possible sarcasm/irony; human context review recommended."
        result.suggested_action = "human_review"
        return result

    if not result.categories:
        if any(m in lowered for m in OPINION_MARKERS) or len(text.split()) < 4:
            result.categories.append("not_actionable")
            result.suggested_action = "no_action"
        else:
            result.categories.append("uncertain_context_needed")
            result.suggested_action = "human_review"

    # De-duplicate while preserving order.
    result.categories = list(dict.fromkeys(result.categories))
    if "threat_like" in result.categories:
        result.suggested_action = "prioritize_review"
    elif "spam" in result.categories:
        result.suggested_action = "queue_spam_review"

    if not result.explanation:
        result.explanation = (
            f"Heuristic label(s): {', '.join(result.categories)}. Rule-based v1, uncalibrated on "
            "representative Hindi/Hinglish data; a human reviewer confirms before any external action."
        )
    if quoted:
        result.explanation += " Quotation markers detected — speaker may be reporting/condemning the wording."
    return result


def analyze_and_store(db: Session, case_id: str, comment_id: str) -> CommentAnalysis:
    comment = db.get(Comment, comment_id)
    if comment is None or comment.case_id != case_id:
        raise KeyError("comment not in case")
    parent = db.get(Comment, comment.parent_comment_id) if comment.parent_comment_id else None
    result = analyze_comment_text(comment.raw_text, parent.raw_text if parent else "")
    existing = db.scalar(select(CommentAnalysis).where(
        CommentAnalysis.case_id == case_id, CommentAnalysis.comment_id == comment_id))
    if existing:
        existing.categories = json.dumps(result.categories, ensure_ascii=False)
        existing.evidence_spans = json.dumps(result.spans, ensure_ascii=False)
        existing.explanation = result.explanation
        existing.scores = json.dumps(result.scores)
        existing.suggested_action = result.suggested_action
        db.flush()
        return existing
    record = CommentAnalysis(
        case_id=case_id, comment_id=comment_id,
        categories=json.dumps(result.categories, ensure_ascii=False),
        evidence_spans=json.dumps(result.spans, ensure_ascii=False),
        explanation=result.explanation,
        scores=json.dumps(result.scores),
        suggested_action=result.suggested_action,
    )
    db.add(record)
    db.flush()
    return record
