"""Disposable Docker Compose infrastructure smoke test (no external sources).

The CI workflow runs this only against the local Compose stack and then removes
its volumes. It verifies real Postgres persistence, MinIO snapshot upload and a
Celery worker transition; it never substitutes local thread execution.
"""
from __future__ import annotations

import base64
import os
import time

import httpx

BASE = os.environ.get("SCAMURAI_SMOKE_URL", "http://127.0.0.1:8000")
HEADERS = {"Authorization": "Bearer dev-token-owner"}


def main() -> None:
    deadline = time.time() + 240
    with httpx.Client(base_url=BASE, timeout=15) as client:
        while True:
            try:
                health = client.get("/health")
                if health.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if time.time() > deadline:
                raise SystemExit("API did not become healthy within 240 seconds")
            time.sleep(3)
        payload = health.json()
        assert payload["job_runner"] == "celery", payload
        assert payload["storage_backend"] == "s3", payload

        case = client.post("/api/v1/cases", headers=HEADERS, json={
            "title": "Disposable Compose infrastructure smoke",
            "purpose": "Verify local ephemeral Postgres, MinIO and Celery wiring",
            "languages": ["en"], "member_emails": [], "member_roles": {},
        })
        assert case.status_code == 201, case.text
        case_id = case.json()["id"]

        # Empty authorized bundle still writes a real raw snapshot to MinIO and
        # its metadata to Postgres. No analytics or synthetic finding is made.
        upload = client.post(
            f"/api/v1/cases/{case_id}/uploads", headers=HEADERS,
            files={"file": ("smoke.json", b'{"platform":"compose-smoke","accounts":[],"posts":[]}',
                            "application/json")},
            data={"kind": "json", "meta": "{}"}, timeout=30)
        assert upload.status_code == 201, upload.text

        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")
        media = client.post(
            f"/api/v1/cases/{case_id}/uploads", headers=HEADERS,
            files={"file": ("smoke-pixel.png", png, "image/png")},
            data={"kind": "image", "meta": "{}"}, timeout=30)
        assert media.status_code == 201, media.text

        run = client.post(f"/api/v1/cases/{case_id}/runs", headers=HEADERS, json={
            "workflow": "media_forensics", "client_idempotency_key": "compose-smoke-media"})
        assert run.status_code == 202, run.text
        job_id = run.json()["job_id"]
        job_deadline = time.time() + 120
        while True:
            job_response = client.get(f"/api/v1/cases/{case_id}/jobs/{job_id}", headers=HEADERS)
            assert job_response.status_code == 200, job_response.text
            job = job_response.json()
            if job["lifecycle"] in {"completed", "failed", "cancelled"}:
                break
            if time.time() > job_deadline:
                raise SystemExit(f"Celery job did not finish: {job}")
            time.sleep(2)
        assert job["lifecycle"] == "completed", job
        forensic_response = client.get(f"/api/v1/cases/{case_id}/media/forensics", headers=HEADERS)
        assert forensic_response.status_code == 200, forensic_response.text
        forensic = next((row for row in forensic_response.json()
                         if row["filename"] == "smoke-pixel.png"), None)
        assert forensic is not None, forensic_response.json()
        assert forensic["model_result"]["status"] == "not_configured", forensic
        raw = client.get(
            f"/api/v1/cases/{case_id}/media/{forensic['media_asset_id']}/raw", headers=HEADERS)
        assert raw.status_code == 200 and raw.content == png, "S3 media readback differed"
        print(f"Compose smoke passed: case={case_id}, job={job_id}, outcome={job['outcome']}; "
              "S3 snapshot upload + media readback + Celery forensics verified")


if __name__ == "__main__":
    main()
