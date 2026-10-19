"""HTTP-level tests for the bounded agent endpoint."""
from __future__ import annotations

import time
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_agent_image_goal_enqueues_bounded_jobs(client, auth, make_case, upload_file, image_dir):
    case_id = make_case()
    upload_file(case_id, image_dir / "scene_a.png", "image")
    upload_file(case_id, image_dir / "scene_a_recompressed.jpg", "image")

    r = client.post(
        f"/api/v1/cases/{case_id}/agent/run", headers=auth(),
        json={"goal": "image_source", "client_idempotency_key": "agent-img-0001"})
    assert r.status_code == 202, r.text
    body = r.json()
    # OCR is an external provider and is honestly disabled, ending the plan.
    assert body["stop_reason"] in ("external_provider_disabled", "completed")
    tools = [s["tool"] for s in body["steps"]]
    assert "compare_images" in tools
    assert "extract_ocr" in tools
    ocr_step = next(s for s in body["steps"] if s["tool"] == "extract_ocr")
    assert ocr_step["ok"] is False and "provider" in (ocr_step["limitation"] or "").lower()

    # The image-matching job dispatched by the agent actually runs.
    for job in body["jobs"]:
        if job["kind"] == "agent:image_matching":
            deadline = time.time() + 30
            while time.time() < deadline:
                current = client.get(
                    f"/api/v1/cases/{case_id}/jobs/{job['id']}", headers=auth()).json()
                if current["lifecycle"] in ("completed", "failed", "cancelled"):
                    assert current["lifecycle"] == "completed"
                    break
                time.sleep(0.2)
            else:
                raise AssertionError("agent-dispatched job did not finish")


def test_agent_unknown_goal_and_rbac(client, auth, make_case):
    case_id = make_case()
    r = client.post(
        f"/api/v1/cases/{case_id}/agent/run", headers=auth(),
        json={"goal": "exfiltrate all cases", "client_idempotency_key": "agent-bad-0001"})
    assert r.status_code == 202
    assert r.json()["stop_reason"] == "unknown_goal"

    # Viewers cannot drive the agent.
    r2 = client.post(
        f"/api/v1/cases/{case_id}/agent/run", headers=auth("viewer"),
        json={"goal": "coordination", "client_idempotency_key": "agent-rbac-001"})
    assert r2.status_code in (403, 404)
