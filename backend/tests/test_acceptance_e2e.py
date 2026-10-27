"""End-to-end acceptance tests (master prompt section 21, gate #9).

A complete synthetic case is created, analyzed, reviewed, exported, reopened
and audited using only authorized local fixtures — no real platforms.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture()
def populated_case(client, auth, make_case, upload_file, image_dir):
    case_id = make_case(members={"reviewer@scamurai.local": "reviewer", "viewer@scamurai.local": "viewer"})
    for name in ("scene_a.png", "scene_a_renamed.png", "scene_a_recompressed.jpg",
                 "scene_a_crop.png", "scene_b_same_size.jpg", "scene_unrelated.png",
                 "image_with_gps.jpg", "cultural_hall.png"):
        upload_file(case_id, image_dir / name, "image")
    upload_file(case_id, FIXTURES / "posts.json", "json")
    upload_file(case_id, FIXTURES / "comments.csv", "csv",
                meta=json.dumps({"platform_displayed_count": 25, "counts_comparable": False}))
    upload_file(case_id, FIXTURES / "factchecks.json", "json")
    return case_id


def test_full_case_lifecycle(client, auth, populated_case, run_workflow):
    case_id = populated_case

    image_job = run_workflow(case_id, "image_matching", "e2e-image-0001")
    assert image_job["lifecycle"] == "completed"
    comment_job = run_workflow(case_id, "comment_analysis", "e2e-comment-001")
    assert comment_job["lifecycle"] == "completed"
    coord_job = run_workflow(case_id, "coordination_detection", "e2e-coord-001")
    assert coord_job["lifecycle"] == "completed"
    claim_job = run_workflow(case_id, "claim_workflow", "e2e-claim-001")
    assert claim_job["lifecycle"] in ("completed",)
    location_job = run_workflow(case_id, "location_analysis", "e2e-location-1")
    assert location_job["lifecycle"] == "completed"

    # Gate 1: every finding resolves to existing evidence; no invented probability labels.
    findings = client.get(f"/api/v1/cases/{case_id}/findings", headers=auth()).json()
    assert findings
    graph = client.get(f"/api/v1/cases/{case_id}/graph", headers=auth()).json()
    entity_ids = {n["entity_id"] for n in graph["nodes"]}
    for finding in findings:
        assert "probability of disinformation" not in finding["question"]
        for evidence_id in finding["evidence_ids"]:
            assert evidence_id in entity_ids, "finding points at missing evidence"

    # Source-supported edges are never created from unsupported prose.
    for edge in graph["edges"]:
        assert edge["derivation_class"] in ("fact", "similarity", "hypothesis", "note")
        if edge["derivation_class"] == "fact":
            assert edge["relationship"] in {
                "PUBLISHED", "REPLIES_TO", "CONTAINS_MEDIA", "EXACT_FILE_MATCH",
                "PUBLICLY_CROSSLINKS", "GPS_METADATA_REPORTS", "DERIVED_FROM",
                "PRESERVED_AS", "ASSERTS_CLAIM", "LINKS_TO"}


def test_image_pipeline_honesty(client, auth, populated_case, run_workflow):
    run_workflow(populated_case, "image_matching", "img-honesty-001")
    findings = client.get(f"/api/v1/cases/{populated_case}/findings", headers=auth()).json()
    image_findings = [f for f in findings if f["conclusion_category"].startswith("image_match:")]
    categories = {f["conclusion_category"] for f in image_findings}
    assert "image_match:exact_file" in categories
    assert any(c.startswith("image_match:likely_same_visual_source")
               or c.startswith("image_match:partial_region_match") for c in categories)

    # Control: different image with identical byte length must not match.
    stats = client.get(f"/api/v1/cases/{populated_case}/stats", headers=auth()).json()
    assert stats["media"] == 8
    no_match = [f for f in image_findings if f["conclusion_category"] == "image_match:no_match"]
    assert no_match, "same-size different-content images must resolve to no_match"
    for f in no_match:
        assert any("size alone is never a match" in e for e in f["excerpts"])


def test_comment_coverage_and_multilabel(client, auth, populated_case, run_workflow):
    run_workflow(populated_case, "comment_analysis", "comment-ml-001")
    listing = client.get(f"/api/v1/cases/{populated_case}/comments", headers=auth()).json()
    # 16 CSV rows, one duplicate stable id -> 15 unique; two authors writing "Very good" both kept.
    assert listing["total"] == 15
    coverage = listing["coverage"][0]
    assert coverage["coverage_percent"] is None  # non-comparable denominator must never show %
    assert coverage["status"] == "partial_list_denominator_not_comparable_or_unknown"

    by_id = {c["id"]: c for c in listing["items"]}
    analyzed = [c for c in by_id.values() if c["analysis"]]
    categories = {cat for c in analyzed for cat in c["analysis"]["categories"]}
    assert "ordinary_criticism" in categories
    assert "targeted_insult" in categories
    assert "threat_like" in categories
    assert "spam" in categories
    assert "prompt_instruction_in_content" in categories
    # Quoted abuse is labeled as quotation, not as the speaker's own insult.
    quoted = [c for c in analyzed if any(x.startswith("quoted_") for x in c["analysis"]["categories"])]
    assert quoted
    # Negation prevents an insult label.
    fair = [c for c in analyzed if "not stupid" in c["raw_text"]][0]
    assert "targeted_insult" not in fair["analysis"]["categories"]
    # Every analysis declares its uncalibrated validation status.
    assert all(c["analysis"]["validation_status"] == "heuristic-v1-uncalibrated" for c in analyzed)
    # Missing permalink is honest; no guessed URLs.
    no_link = [c for c in by_id.values() if not c["permalink"]]
    assert no_link and all(c["permalink_status"] in ("unavailable", "not_checked") for c in no_link)


def test_coordination_negative_controls(client, auth, populated_case, run_workflow):
    run_workflow(populated_case, "coordination_detection", "coord-neg-0001")
    graph = client.get(f"/api/v1/cases/{populated_case}/graph",
                       headers=auth(), params={"relation_types": "POSSIBLY_COORDINATED_WITH"}).json()
    # Hypothesis edges exist only for the repeated-alignment pair, not hashtag/rain news pairs.
    assert graph["total_edges"] >= 2
    findings = client.get(f"/api/v1/cases/{populated_case}/findings", headers=auth()).json()
    coord = [f for f in findings if f["conclusion_category"].startswith("coordination:")]
    states = {f["conclusion_category"] for f in coord}
    assert "coordination:review_candidate" in states
    assert "coordination:insufficient_evidence" in states
    for f in coord:
        assert any("not proof of shared ownership" in lim for lim in f["limitations"])


def test_claim_verification_separates_outcomes(client, auth, populated_case, run_workflow):
    job = run_workflow(populated_case, "claim_workflow", "claim-out-0001")
    assert job["counts"]["claims"] >= 3
    findings = client.get(f"/api/v1/cases/{populated_case}/findings", headers=auth()).json()
    categories = {f["conclusion_category"] for f in findings}
    assert "refuted" in categories
    assert "supported" in categories
    assert "insufficient_available_evidence" in categories
    # No-search is never called falsity: insufficient findings carry a query plan limitation.
    insufficient = [f for f in findings if f["conclusion_category"] == "insufficient_available_evidence"]
    assert any("No search result is not proof of falsity" in lim
               for f in insufficient for lim in f["limitations"])


def test_location_does_not_invent_places(client, auth, populated_case, run_workflow):
    run_workflow(populated_case, "location_analysis", "loc-accept-001")
    findings = client.get(f"/api/v1/cases/{populated_case}/findings", headers=auth()).json()
    locations = [f for f in findings if f["conclusion_category"].startswith("location:")]
    statuses = {f["conclusion_category"] for f in locations}
    assert "location:metadata_reported" in statuses       # image_with_gps.jpg
    assert "location:insufficient" in statuses            # cultural_hall.png and others
    # Generic CULTURAL CLUB background must not produce a named university.
    hall = [f for f in locations if "cultural_hall" in f["question"]][0]
    assert hall["conclusion_category"] == "location:insufficient"
    assert not any("university" in e.lower() for e in hall["excerpts"])


def test_review_rbac_and_exports(client, auth, populated_case, run_workflow):
    run_workflow(populated_case, "image_matching", "rbac-image-001")
    run_workflow(populated_case, "comment_analysis", "rbac-comment-01")
    finding = client.get(f"/api/v1/cases/{populated_case}/findings", headers=auth()).json()[0]

    # Viewers cannot review or export.
    r = client.post(f"/api/v1/cases/{populated_case}/findings/{finding['id']}/reviews",
                    headers=auth("viewer"), json={"decision": "accepted", "note": "x"})
    assert r.status_code == 403
    r = client.post(f"/api/v1/cases/{populated_case}/exports",
                    headers=auth("viewer"), json={"fmt": "json", "redaction_mode": "redacted"})
    assert r.status_code == 403

    # Reviewer accepts a finding.
    r = client.post(f"/api/v1/cases/{populated_case}/findings/{finding['id']}/reviews",
                    headers=auth("reviewer"), json={"decision": "accepted", "note": "evidence ok"})
    assert r.status_code == 200

    for fmt in ("json", "csv", "html", "pdf"):
        r = client.post(f"/api/v1/cases/{populated_case}/exports", headers=auth(),
                        json={"fmt": fmt, "redaction_mode": "redacted"})
        assert r.status_code == 202, r.text
        export = r.json()
        assert export["sha256"] and len(export["sha256"]) == 64
        dl = client.get(f"/api/v1/cases/{populated_case}/exports/{export['id']}/download",
                        headers=auth())
        assert dl.status_code == 200 and len(dl.content) > 100

    # CSV formula injection is neutralized (comment C-015 starts with =1+1).
    r = client.post(f"/api/v1/cases/{populated_case}/exports", headers=auth(),
                    json={"fmt": "csv", "redaction_mode": "full"})
    csv_blob = client.get(
        f"/api/v1/cases/{populated_case}/exports/{r.json()['id']}/download",
        headers=auth()).content.decode()
    assert "'=1+1" in csv_blob and "\n=1+1" not in csv_blob

    # Audit trail records the key actions.
    audit = client.get(f"/api/v1/cases/{populated_case}/audit", headers=auth()).json()
    actions = {e["action"] for e in audit}
    assert {"case.create", "finding.review", "export.create"}.issubset(actions)


def test_idempotent_runs_and_reopening(client, auth, populated_case, run_workflow):
    first = run_workflow(populated_case, "comment_analysis", "idem-key-0001")
    assert first["lifecycle"] == "completed", first
    # Replay with the same client idempotency key returns the same job, no duplicate effects.
    r = client.post(f"/api/v1/cases/{populated_case}/runs", headers=auth(),
                    json={"workflow": "comment_analysis", "client_idempotency_key": "idem-key-0001"})
    assert r.status_code == 202 and r.json()["replayed"] is True
    stats1 = client.get(f"/api/v1/cases/{populated_case}/stats", headers=auth()).json()
    run_workflow(populated_case, "comment_analysis", "idem-key-0002")
    stats2 = client.get(f"/api/v1/cases/{populated_case}/stats", headers=auth()).json()
    assert stats1 == stats2  # duplicate-safe workers

    # Reopening the case: graph and evidence still resolve.
    graph = client.get(f"/api/v1/cases/{populated_case}/graph", headers=auth()).json()
    assert graph["total_nodes"] > 5 and graph["total_edges"] > 5
