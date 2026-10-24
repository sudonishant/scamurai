"""Reproducible multilingual diagnostic for the production lexical method.

This intentionally evaluates TF-IDF/cosine behavior, not a semantic embedding
model. The bundled synthetic pairs are a small smoke/diagnostic set, not a
representative accuracy benchmark or evidence of coordination.
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.services.analytics import _cosine, _tfidf_vectors  # noqa: E402
from app.services.textutil import normalize_text  # noqa: E402

FIXTURE = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "multilingual_narratives.json"
PRODUCTION_THRESHOLD = 0.48
VALID_LABELS = {"same_narrative", "different_narrative"}


def _metrics(rows: list[dict]) -> dict:
    tp = sum(row["label"] == "same_narrative" and row["predicted_same_candidate"] for row in rows)
    fp = sum(row["label"] == "different_narrative" and row["predicted_same_candidate"] for row in rows)
    tn = sum(row["label"] == "different_narrative" and not row["predicted_same_candidate"] for row in rows)
    fn = sum(row["label"] == "same_narrative" and not row["predicted_same_candidate"] for row in rows)

    def ratio(numerator: int, denominator: int) -> float | None:
        return round(numerator / denominator, 4) if denominator else None

    return {
        "pairs": len(rows),
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "precision": ratio(tp, tp + fp),
        "recall": ratio(tp, tp + fn),
        "f1": (round(2 * tp / (2 * tp + fp + fn), 4) if 2 * tp + fp + fn else None),
        "empty_token_pairs": sum(not row["lexical_scorable"] for row in rows),
    }


def evaluate(fixture_path: pathlib.Path = FIXTURE) -> dict:
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    if fixture.get("synthetic") is not True:
        raise ValueError("Evaluation fixture must be explicitly labelled synthetic")
    if fixture.get("threshold") != PRODUCTION_THRESHOLD:
        raise ValueError("Fixture threshold must match the production lexical candidate threshold")
    pairs = fixture.get("pairs") or []
    if not pairs:
        raise ValueError("Evaluation fixture has no pairs")
    ids = [row.get("id") for row in pairs]
    if len(ids) != len(set(ids)) or any(not value for value in ids):
        raise ValueError("Pair IDs must be present and unique")
    for row in pairs:
        if row.get("label") not in VALID_LABELS or not row.get("left") or not row.get("right"):
            raise ValueError(f"Invalid labelled pair: {row.get('id')}")

    # One corpus-level IDF space, matching how a case's collected posts are vectorized.
    unique_texts = list(dict.fromkeys(text for row in pairs for text in (row["left"], row["right"])))
    posts = [SimpleNamespace(id=f"eval-{index}", raw_text=text, normalized_text=normalize_text(text))
             for index, text in enumerate(unique_texts)]
    vectors, token_sets = _tfidf_vectors(posts)
    index_by_text = {post.raw_text: index for index, post in enumerate(posts)}

    results = []
    for pair in pairs:
        left_index = index_by_text[pair["left"]]
        right_index = index_by_text[pair["right"]]
        scorable = bool(token_sets[left_index] and token_sets[right_index])
        exact = bool(scorable and posts[left_index].normalized_text == posts[right_index].normalized_text)
        similarity = 1.0 if exact else _cosine(vectors[left_index], vectors[right_index]) if scorable else 0.0
        if not math.isfinite(similarity) or not 0 <= similarity <= 1:
            raise ValueError(f"Invalid cosine result for {pair['id']}")
        predicted = bool(scorable and similarity >= PRODUCTION_THRESHOLD)
        results.append({
            "id": pair["id"],
            "track": pair["track"],
            "languages": pair["languages"],
            "label": pair["label"],
            "control": pair.get("control"),
            "lexical_cosine": round(similarity, 6),
            "lexical_scorable": scorable,
            "predicted_same_candidate": predicted,
            "shared_tokens": sorted(token_sets[left_index] & token_sets[right_index])[:20],
            "correct": predicted == (pair["label"] == "same_narrative"),
        })

    tracks = sorted({row["track"] for row in results})
    return {
        "schema_version": 1,
        "synthetic_diagnostic": True,
        "fixture": fixture_path.name,
        "method": {
            "name": "case-corpus Unicode-token TF-IDF cosine",
            "candidate_threshold": PRODUCTION_THRESHOLD,
            "exact_normalized_text": True,
            "semantic_embedding_model": "not_configured",
            "cross_lingual_semantic_score": "unavailable_not_zero",
        },
        "summary": _metrics(results),
        "by_track": {track: _metrics([row for row in results if row["track"] == track]) for track in tracks},
        "pairs": results,
        "interpretation": [
            "Small synthetic diagnostic only; these numbers are not production accuracy, calibration, or subgroup benchmarks.",
            "Cross-lingual pairs measure where the lexical method misses semantic equivalence; lexical cosine is not semantic similarity.",
            "A same-narrative candidate does not establish coordination, malicious intent, common ownership, or truth.",
            "Use representative event/account-separated labelled data and a reviewed multilingual model for semantic evaluation.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=pathlib.Path, default=FIXTURE)
    parser.add_argument("--output", type=pathlib.Path, help="Write the complete JSON report to this path")
    parser.add_argument("--json", action="store_true", help="Print complete JSON instead of the compact summary")
    args = parser.parse_args()
    report = evaluate(args.fixture)
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    if args.json:
        print(serialized, end="")
        return
    print("SYNTHETIC DIAGNOSTIC — not production accuracy or a coordination benchmark")
    print(json.dumps(report["summary"], indent=2))
    for track, metrics in report["by_track"].items():
        print(f"{track}: {json.dumps(metrics)}")
    for row in report["pairs"]:
        print(f"{row['id']}: lexical_cosine={row['lexical_cosine']:.3f} "
              f"label={row['label']} predicted_same={row['predicted_same_candidate']} "
              f"{'OK' if row['correct'] else 'REVIEW'}")
    if args.output:
        print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
