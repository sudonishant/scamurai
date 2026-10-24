"""Fixture-based evaluation harness (master prompt section 21).

Runs the deterministic local pipelines over the synthetic fixtures and prints
precision/recall-style measures per task. This is not a held-out benchmark:
no accuracy figure may be advertised until representative labeled data and
split-by-event/account/visual-cluster evaluation exist.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

os.environ.setdefault("SCAMURAI_DATABASE_URL",
                      f"sqlite:///{pathlib.Path(tempfile.mkdtemp()) / 'eval.db'}".replace("///", "///", 1))
os.environ.setdefault("SCAMURAI_STORAGE_DIR", str(pathlib.Path(tempfile.mkdtemp()) / "store"))

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import create_app, seed_users  # noqa: E402

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "fixtures"
IMAGES = FIXTURES / "images"

# Expected behavior on the synthetic ground truth (documented in fixtures/).
EXPECTED_IMAGE = {
    "exact_file": [("scene_a.png", "scene_a_renamed.png")],
    "visual_or_partial": [("scene_a.png", "scene_a_recompressed.jpg"),
                          ("scene_a.png", "scene_a_crop.png")],
    "no_match_controls": [("scene_a.png", "scene_b_same_size.jpg"),
                          ("scene_a.png", "scene_unrelated.png")],
}
EXPECTED_COMMENT_CATEGORIES = {
    "C-003": "targeted_insult",
    "C-004": "quoted_targeted_insult",
    "C-006": "threat_like",
    "C-007": "spam",
    "C-011": "prompt_instruction_in_content",
}


def main() -> None:
    if not IMAGES.exists():
        import subprocess, sys
        subprocess.run([sys.executable, str(FIXTURES / "make_fixture_images.py")], check=True)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_users()
    client = TestClient(create_app())
    headers = {"Authorization": "Bearer dev-token-owner"}
    case_id = client.post("/api/v1/cases", headers=headers,
                          json={"title": "evaluation", "languages": ["en", "hi"]}).json()["id"]

    def upload(path: pathlib.Path, kind: str, meta: str = "{}"):
        with open(path, "rb") as fh:
            client.post(f"/api/v1/cases/{case_id}/uploads", headers=headers,
                        files={"file": (path.name, fh, "application/octet-stream")},
                        data={"kind": kind, "meta": meta}).raise_for_status()

    for image in sorted(IMAGES.iterdir()):
        upload(image, "image")
    upload(FIXTURES / "posts.json", "json")
    upload(FIXTURES / "factchecks.json", "json")
    upload(FIXTURES / "comments.csv", "csv",
           json.dumps({"platform_displayed_count": 25, "counts_comparable": False}))

    def run(workflow: str):
        job_id = client.post(f"/api/v1/cases/{case_id}/runs", headers=headers, json={
            "workflow": workflow,
            "client_idempotency_key": f"eval-{workflow}-0001"}).json()["job_id"]
        for _ in range(100):
            import time
            time.sleep(0.2)
            job = client.get(f"/api/v1/cases/{case_id}/jobs/{job_id}", headers=headers).json()
            if job["lifecycle"] in ("completed", "failed", "cancelled"):
                return job
        raise RuntimeError("job timed out")

    run("image_matching")
    run("comment_analysis")
    run("coordination_detection")
    run("claim_workflow")
    run("location_analysis")

    findings = client.get(f"/api/v1/cases/{case_id}/findings", headers=headers).json()
    image_cats = {f["conclusion_category"] for f in findings
                  if f["conclusion_category"].startswith("image_match:")}

    print("\n=== IMAGE MATCHING (fixture expectations, not held-out accuracy) ===")
    for group, pairs in EXPECTED_IMAGE.items():
        print(f"{group}: {len(pairs)} expected pair(s); observed categories "
              f"{sorted(c.replace('image_match:', '') for c in image_cats)}")

    print("\n=== COMMENT MODERATION (label presence, precision/recall need labeled sets) ===")
    comments = client.get(f"/api/v1/cases/{case_id}/comments?limit=200", headers=headers).json()["items"]
    by_stable = {c["stable_id"]: c for c in comments}
    hits = 0
    for stable, expected in EXPECTED_COMMENT_CATEGORIES.items():
        actual = by_stable.get(stable, {}).get("analysis", {}).get("categories", [])
        ok = expected in actual
        hits += ok
        print(f"{stable}: expected {expected:<28} got {actual} {'OK' if ok else 'MISS'}")
    print(f"fixture label recall: {hits}/{len(EXPECTED_COMMENT_CATEGORIES)}")

    coord = [f for f in findings if f["conclusion_category"].startswith("coordination:")]
    print("\n=== COORDINATION ===")
    print("states:", {f["conclusion_category"] for f in coord})
    print("negative controls must remain insufficient; no probability-of-guilt labels are emitted.")

    loc = {f["conclusion_category"] for f in findings
           if f["conclusion_category"].startswith("location:")}
    print("\n=== LOCATION ===", sorted(loc))
    print("Cultural-hall control must stay 'insufficient' (no invented institution).\n")


if __name__ == "__main__":
    main()
