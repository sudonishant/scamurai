"""Graph navigation, comparison matrix and transform policy tests."""
from __future__ import annotations

import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _populate(client, auth, make_case, upload_file, image_dir):
    case_id = make_case()
    upload_file(case_id, image_dir / "scene_a.png", "image")
    upload_file(case_id, image_dir / "scene_a_recompressed.jpg", "image")
    upload_file(case_id, FIXTURES / "posts.json", "json")
    return case_id


def test_shortest_known_evidence_path(client, auth, make_case, upload_file, image_dir,
                                      run_workflow):
    case_id = _populate(client, auth, make_case, upload_file, image_dir)
    run_workflow(case_id, "image_matching", "path-img-0001")
    graph = client.get(f"/api/v1/cases/{case_id}/graph", headers=auth()).json()
    nodes = graph["nodes"]
    source = nodes[0]["id"]
    target = nodes[-1]["id"]
    r = client.post(f"/api/v1/cases/{case_id}/graph/path", headers=auth(),
                    json={"source_node_id": source, "target_node_id": target,
                          "max_depth": 8, "max_nodes": 100})
    assert r.status_code == 200
    body = r.json()
    assert body["disclaimer"].startswith("Navigation aid")
    assert isinstance(body["edges"], list)
    # Impossible target yields an empty path, not a fabricated relationship.
    r2 = client.post(f"/api/v1/cases/{case_id}/graph/path", headers=auth(),
                     json={"source_node_id": source, "target_node_id": "does-not-exist",
                           "max_depth": 4, "max_nodes": 30})
    assert r2.json()["found"] is False


def test_pairwise_comparison_matrix(client, auth, make_case, upload_file, image_dir):
    case_id = _populate(client, auth, make_case, upload_file, image_dir)
    accounts = client.get(f"/api/v1/cases/{case_id}/graph", headers=auth()).json()["nodes"]
    account_ids = [n["entity_id"] for n in accounts if n["entity_type"] == "account"]
    assert len(account_ids) == 4
    r = client.get(f"/api/v1/cases/{case_id}/compare",
                   headers=auth(), params={"account_ids": ",".join(account_ids[:3])})
    assert r.status_code == 200
    body = r.json()
    assert body["pair_count"] == 3  # three accounts -> three distinct pairs
    for pair in body["pairs"]:
        assert set(pair.keys()) == {"pair", "identity_verified", "shared_content",
                                    "explicit_public_crosslinks", "timing_indicators",
                                    "contradictory_or_insufficient"}
        assert pair["contradictory_or_insufficient"]


def test_transform_registry_and_disabled_providers(client, auth, make_case, upload_file,
                                                   image_dir, wait_job):
    case_id = _populate(client, auth, make_case, upload_file, image_dir)
    graph = client.get(f"/api/v1/cases/{case_id}/graph", headers=auth()).json()
    media_node = next(n for n in graph["nodes"] if n["entity_type"] == "media")

    # Invalid entity/transform pairing is rejected with 422.
    r = client.post(f"/api/v1/cases/{case_id}/transforms", headers=auth(),
                    json={"transform": "analyze_comment", "entity_type": "media",
                          "entity_id": media_node["entity_id"],
                          "client_idempotency_key": "bad-transform-001"})
    assert r.status_code == 422

    # OCR has no provider: the job completes honestly as insufficient evidence.
    r = client.post(f"/api/v1/cases/{case_id}/transforms", headers=auth(),
                    json={"transform": "extract_ocr", "entity_type": "media",
                          "entity_id": media_node["entity_id"],
                          "client_idempotency_key": "ocr-transform-001"})
    assert r.status_code == 202 and r.json()["provider_warning"] == "external provider required"
    job = wait_job(case_id, r.json()["job_id"])
    assert job["outcome"] == "insufficient_evidence"
    assert any("no approved provider" in lim for lim in job["limitations"])


def test_layout_pin_does_not_create_relationship(client, auth, make_case, upload_file, image_dir):
    case_id = _populate(client, auth, make_case, upload_file, image_dir)
    graph_before = client.get(f"/api/v1/cases/{case_id}/graph", headers=auth()).json()
    node = graph_before["nodes"][0]
    r = client.post(f"/api/v1/cases/{case_id}/graph/nodes/{node['id']}/pin",
                    headers=auth(), params={"pinned": True})
    assert r.status_code == 200
    graph_after = client.get(f"/api/v1/cases/{case_id}/graph", headers=auth()).json()
    assert graph_after["total_edges"] == graph_before["total_edges"]
