"""Test configuration: isolated temp DB/storage and synthetic fixtures."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="scamurai-test-"))
os.environ["SCAMURAI_DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"
os.environ["SCAMURAI_STORAGE_DIR"] = str(_TMP / "storage")
os.environ["SCAMURAI_DEV_AUTH_ENABLED"] = "true"
os.environ["SCAMURAI_OCR_PROVIDER"] = ""
os.environ["SCAMURAI_REVERSE_SEARCH_PROVIDER"] = ""
os.environ["SCAMURAI_LLM_PROVIDER"] = ""
# Provider credentials must never leak from a developer's .env into the test run.
for _var in ("SCAMURAI_LLM_API_KEY", "SCAMURAI_LLM_BASE_URL", "SCAMURAI_LLM_MODEL_ID",
             "SCAMURAI_GEMINI_API_KEY", "SCAMURAI_YOUTUBE_API_KEY",
             "SCAMURAI_GOOGLE_FACTCHECK_API_KEY", "SCAMURAI_REDDIT_CLIENT_ID",
             "SCAMURAI_REDDIT_CLIENT_SECRET", "SCAMURAI_REDDIT_USER_AGENT"):
    os.environ[_var] = ""

BACKEND = Path(__file__).resolve().parents[1]
FIXTURES = BACKEND / "fixtures"
sys.path.insert(0, str(BACKEND))


def _ensure_images() -> Path:
    images = FIXTURES / "images"
    if not images.exists() or not list(images.glob("*.png")):
        subprocess.run([sys.executable, str(FIXTURES / "make_fixture_images.py")], check=True)
    return images


@pytest.fixture(scope="session", autouse=True)
def _images():
    _ensure_images()


@pytest.fixture(scope="session")
def image_dir():
    return _ensure_images()


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from sqlalchemy import text
    from app.database import Base, engine, upgrade_db
    from app.main import create_app, seed_users
    from app.services.jobs import reconcile_orphans

    Base.metadata.drop_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    upgrade_db()
    seed_users()
    reconcile_orphans()
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


TOKENS = {
    "owner": "dev-token-owner",
    "analyst": "dev-token-analyst",
    "reviewer": "dev-token-reviewer",
    "viewer": "dev-token-viewer",
}


@pytest.fixture()
def auth():
    def _headers(role: str = "owner") -> dict:
        return {"Authorization": f"Bearer {TOKENS[role]}"}
    return _headers


@pytest.fixture()
def make_case(client, auth):
    def _make(title: str = "Synthetic investigation", owner: str = "owner",
              members: dict[str, str] | None = None) -> str:
        payload = {"title": title, "purpose": "Detect coordinated behavior in synthetic corpus",
                   "languages": ["en", "hi"],
                   "member_emails": list((members or {}).keys()),
                   "member_roles": members or {}}
        r = client.post("/api/v1/cases", headers=auth(owner), json=payload)
        assert r.status_code == 201, r.text
        return r.json()["id"]
    return _make


@pytest.fixture()
def upload_file(client, auth):
    def _upload(case_id: str, path: Path, kind: str, role: str = "owner", meta: str = "{}"):
        with open(path, "rb") as fh:
            r = client.post(
                f"/api/v1/cases/{case_id}/uploads",
                headers=auth(role),
                files={"file": (path.name, fh, "application/octet-stream")},
                data={"kind": kind, "meta": meta})
        assert r.status_code == 201, r.text
        return r.json()
    return _upload


@pytest.fixture()
def wait_job(client, auth):
    def _wait(case_id: str, job_id: str, timeout: float = 30.0) -> dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            r = client.get(f"/api/v1/cases/{case_id}/jobs/{job_id}", headers=auth())
            assert r.status_code == 200
            job = r.json()
            if job["lifecycle"] in ("completed", "failed", "cancelled"):
                return job
            time.sleep(0.15)
        raise AssertionError("job did not finish in time")
    return _wait


@pytest.fixture()
def run_workflow(client, auth, wait_job):
    def _run(case_id: str, workflow: str, key: str) -> dict:
        r = client.post(f"/api/v1/cases/{case_id}/runs", headers=auth(),
                        json={"workflow": workflow, "client_idempotency_key": key})
        assert r.status_code == 202, r.text
        return wait_job(case_id, r.json()["job_id"])
    return _run
