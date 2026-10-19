"""Create a fully populated demo case from the authorized synthetic fixtures.

Usage (with the API already running):
    python scripts/seed_demo.py
or standalone against a fresh database:
    python scripts/seed_demo.py --direct
Everything is synthetic and clearly labeled — no real accounts or people.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "fixtures"
IMAGES = FIXTURES / "images"


def _ensure_images() -> None:
    if not IMAGES.exists() or not list(IMAGES.glob("*.png")):
        import subprocess
        subprocess.run([sys.executable, str(FIXTURES / "make_fixture_images.py")], check=True)


def seed_over_http(base: str = "http://127.0.0.1:8000", token: str = "dev-token-owner") -> str:
    import httpx
    _ensure_images()
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=base, timeout=60) as client:
        case_id = client.post("/api/v1/cases", headers=headers, json={
            "title": "Demo: rain-photo coordination investigation",
            "purpose": "Synthetic authorized corpus demonstrating the full evidence pipeline",
            "languages": ["en", "hi"],
        }).json()["id"]

        def upload(path: pathlib.Path, kind: str, meta: str = "{}") -> None:
            with open(path, "rb") as fh:
                r = client.post(
                    f"/api/v1/cases/{case_id}/uploads", headers=headers,
                    files={"file": (path.name, fh, "application/octet-stream")},
                    data={"kind": kind, "meta": meta})
                r.raise_for_status()

        for image in sorted(IMAGES.iterdir()):
            upload(image, "image")
        upload(FIXTURES / "posts.json", "json")
        upload(FIXTURES / "factchecks.json", "json")
        upload(FIXTURES / "comments.csv", "csv",
               json.dumps({"platform_displayed_count": 25, "counts_comparable": False}))

        for i, workflow in enumerate(["image_matching", "comment_analysis",
                                      "coordination_detection", "claim_workflow",
                                      "location_analysis"]):
            r = client.post(f"/api/v1/cases/{case_id}/runs", headers=headers, json={
                "workflow": workflow,
                "client_idempotency_key": f"seed-{workflow}-0001",
            })
            job_id = r.json()["job_id"]
            for _ in range(100):
                time.sleep(0.4)
                job = client.get(f"/api/v1/cases/{case_id}/jobs/{job_id}", headers=headers).json()
                if job["lifecycle"] in ("completed", "failed", "cancelled"):
                    print(f"{workflow}: {job['lifecycle']}/{job['outcome']} {job['counts']}")
                    break
        print(f"\nDemo case id: {case_id}")
        print(f"Open: {base}/api/v1/cases/{case_id}/graph")
        return case_id


if __name__ == "__main__":
    seed_over_http(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000")
