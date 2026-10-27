"""Regression tests for production infrastructure and investigation operations."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select

from app import security
from app.config import Settings
from app.database import SessionLocal
from app.models import User
from app.services import jobs, storage


def _bundle():
    accounts = [{"handle": handle, "platform_id": handle,
                 "profile_url": f"https://example.social/{handle}"}
                for handle in ("alpha", "beta", "gamma")]
    times = ["00:05", "01:05", "02:05", "03:01", "03:02", "03:03"]
    handles = ["alpha", "beta", "alpha", "alpha", "beta", "gamma"]
    posts = [{
        "source_id": f"p-{index}", "account_handle": handle,
        "url": f"https://example.social/{handle}/status/{index}",
        "text": "Bridge closed tonight share this urgent public safety update",
        "language": "en", "timestamp": f"2026-10-20T{time}:00+00:00",
        "timestamp_precision": "minute", "collection_status": "authorized_test_import",
        "location": {"name": "Darbhanga", "latitude": 26.1542,
                     "longitude": 85.8918, "precision": "city_reported"},
    } for index, (time, handle) in enumerate(zip(times, handles, strict=True))]
    return {"platform": "example-social", "accounts": accounts, "posts": posts}


def _upload_bundle(client, auth, case_id, bundle, expected=201):
    response = client.post(
        f"/api/v1/cases/{case_id}/uploads", headers=auth(),
        files={"file": ("campaign.json", json.dumps(bundle).encode(), "application/json")},
        data={"kind": "json", "meta": "{}"})
    assert response.status_code == expected, response.text
    return response


def test_production_auth_configuration_is_fail_closed():
    with pytest.raises(ValueError, match="Development tokens"):
        Settings(environment="production", dev_auth_enabled=True)
    with pytest.raises(ValueError, match="OIDC_ISSUER"):
        Settings(environment="production", dev_auth_enabled=False)
    valid = Settings(environment="production", dev_auth_enabled=False,
                     oidc_issuer="https://idp.example.org/",
                     oidc_audience="scamurai-api",
                     oidc_jwks_url="https://idp.example.org/jwks.json")
    assert valid.oidc_algorithm_list == ["RS256"]


def _oidc_setup(client, monkeypatch):
    security._oidc_jwks_client.cache_clear()
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    class FakeJWKS:
        instances = 0

        def __init__(self, *args, **kwargs):
            type(self).instances += 1

        def get_signing_key_from_jwt(self, token):
            return SimpleNamespace(key=private.public_key())

    monkeypatch.setattr(security.jwt, "PyJWKClient", FakeJWKS)
    monkeypatch.setattr(security.settings, "dev_auth_enabled", False)
    monkeypatch.setattr(security.settings, "oidc_issuer", "https://idp.example.org/")
    monkeypatch.setattr(security.settings, "oidc_audience", "scamurai-api")
    monkeypatch.setattr(security.settings, "oidc_jwks_url", "https://idp.example.org/jwks.json")
    monkeypatch.setattr(security.settings, "oidc_algorithms", "RS256")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "owner@scamurai.local"))
        user.auth_issuer = security.settings.oidc_issuer
        user.auth_subject = "owner-subject"
        db.commit()

    def token(subject="owner-subject", audience="scamurai-api", include_exp=True):
        now = datetime.now(UTC)
        claims = {"sub": subject, "iss": security.settings.oidc_issuer,
                  "aud": audience, "iat": now - timedelta(seconds=2)}
        if include_exp:
            claims["exp"] = now + timedelta(minutes=5)
        return jwt.encode(claims, private, algorithm="RS256", headers={"kid": "test-key"})
    return token, FakeJWKS


def test_oidc_signature_claims_provisioning_and_directory(client, monkeypatch, request):
    request.addfinalizer(security._oidc_jwks_client.cache_clear)
    make_token, fake_jwks = _oidc_setup(client, monkeypatch)
    valid = client.get("/api/v1/users", headers={"Authorization": f"Bearer {make_token()}"})
    assert valid.status_code == 200, valid.text
    assert len(valid.json()) == 1
    assert valid.json()[0]["email"] == "owner@scamurai.local"
    assert valid.json()[0].get("token_hint") is None

    wrong_audience = client.get("/api/v1/cases", headers={
        "Authorization": f"Bearer {make_token(audience='another-api')}"})
    assert wrong_audience.status_code == 401
    missing_exp = client.get("/api/v1/cases", headers={
        "Authorization": f"Bearer {make_token(include_exp=False)}"})
    assert missing_exp.status_code == 401
    unprovisioned = client.get("/api/v1/cases", headers={
        "Authorization": f"Bearer {make_token(subject='not-provisioned')}"})
    assert unprovisioned.status_code == 403
    disabled_dev = client.get("/api/v1/cases", headers={
        "Authorization": "Bearer dev-token-owner"})
    assert disabled_dev.status_code == 401
    assert fake_jwks.instances == 1  # repeated requests reuse PyJWT's JWKS cache


def test_redis_configuration_dispatches_real_celery_task(client, auth, make_case, monkeypatch):
    case_id = make_case()
    calls = []

    class FakeCelery:
        def send_task(self, name, args, queue):
            calls.append((name, args, queue))

    monkeypatch.setattr(jobs.settings, "redis_url", "redis://redis:6379/0")
    monkeypatch.setitem(sys.modules, "worker", SimpleNamespace(celery_app=FakeCelery()))
    response = client.post(f"/api/v1/cases/{case_id}/runs", headers=auth(), json={
        "workflow": "media_forensics", "client_idempotency_key": "celery-dispatch-test"})
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]
    assert calls == [("scamurai.execute_job", [job_id, "media_forensics"], "scamurai")]
    job = client.get(f"/api/v1/cases/{case_id}/jobs/{job_id}", headers=auth())
    assert job.json()["lifecycle"] == "queued"


def test_s3_storage_uses_object_contract_and_closes_stream(monkeypatch, tmp_path):
    objects = {}

    class Body:
        def __init__(self, data):
            self.data = data
            self.closed = False

        def read(self):
            return self.data

        def close(self):
            self.closed = True

    class FakeS3:
        body = None

        def put_object(self, Bucket, Key, Body, ContentType):
            objects[(Bucket, Key)] = Body

        def get_object(self, Bucket, Key):
            self.body = Body(objects[(Bucket, Key)])
            return {"Body": self.body}

    fake = FakeS3()
    monkeypatch.setattr(storage.settings, "storage_backend", "s3")
    monkeypatch.setattr(storage.settings, "storage_dir", str(tmp_path))
    monkeypatch.setattr(storage.settings, "s3_bucket", "private-evidence")
    monkeypatch.setattr(storage, "_s3_client", lambda: fake)
    key = storage.put_object("case-1", "snapshots/evidence.json", b'{"real":true}')
    assert key == "case-1/snapshots/evidence.json"
    assert storage.get_object(key) == b'{"real":true}'
    assert fake.body.closed
    with pytest.raises(RuntimeError, match="local path"):
        storage.object_path(key)
    assert not (tmp_path / "case-1").exists()


def test_alert_review_persists_and_is_audited(client, auth, make_case):
    case_id = make_case(members={
        "reviewer@scamurai.local": "reviewer",
        "viewer@scamurai.local": "viewer",
    })
    _upload_bundle(client, auth, case_id, _bundle())
    analytics = client.get(f"/api/v1/cases/{case_id}/analytics", headers=auth())
    alert = next(row for row in analytics.json()["alerts"]
                 if row["type"] == "narrative_acceleration")
    assert alert["active"] is True
    assert alert["evidence_confidence"]["score_type"].endswith("not_truth_probability")
    denied = client.post(f"/api/v1/cases/{case_id}/alerts/{alert['id']}/review",
                         headers=auth("viewer"), json={"status": "acknowledged", "note": "no"})
    assert denied.status_code == 403
    reviewed = client.post(f"/api/v1/cases/{case_id}/alerts/{alert['id']}/review",
                           headers=auth("reviewer"),
                           json={"status": "acknowledged", "note": "Checking source coverage"})
    assert reviewed.status_code == 200, reviewed.text
    refreshed = client.get(f"/api/v1/cases/{case_id}/analytics", headers=auth())
    persisted = next(row for row in refreshed.json()["alerts"] if row["id"] == alert["id"])
    assert persisted["status"] == "acknowledged"
    assert persisted["review_note"] == "Checking source coverage"
    queue = client.get(f"/api/v1/cases/{case_id}/alerts?active=true", headers=auth("reviewer"))
    assert any(row["id"] == alert["id"] for row in queue.json())
    audit = client.get(f"/api/v1/cases/{case_id}/audit", headers=auth())
    assert any(row["action"] == "alert.review" for row in audit.json())


def test_geo_group_threshold_counts_subjects_not_post_volume(client, auth, make_case):
    case_id = make_case()
    bundle = _bundle()
    for index, post in enumerate(bundle["posts"]):
        post["account_handle"] = "alpha"
        post["source_id"] = f"single-{index}"
    _upload_bundle(client, auth, case_id, bundle)
    body = client.get(f"/api/v1/cases/{case_id}/analytics", headers=auth()).json()
    assert body["coverage"]["geolocated_posts"] == 6
    assert body["geospatial"]["points"] == []
    assert body["geospatial"]["privacy"]["suppressed_groups"] == 1
    assert body["geospatial"]["privacy"]["suppressed_observations"] == 6


def test_account_detail_search_metrics_and_reimport_provenance(client, auth, make_case):
    case_id = make_case()
    bundle = _bundle()
    bundle["accounts"][0]["public_crosslinks"] = ["beta"]
    bundle["accounts"][1]["public_crosslinks"] = ["gamma"]
    _upload_bundle(client, auth, case_id, bundle)
    accounts = client.get(f"/api/v1/cases/{case_id}/accounts?q=alpha", headers=auth())
    assert accounts.status_code == 200
    account_id = accounts.json()[0]["id"]
    detail = client.get(f"/api/v1/cases/{case_id}/accounts/{account_id}", headers=auth())
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["summary"]["post_count"] == 3
    assert body["behavior"]["score_type"] == "transparent_heuristic_not_bot_probability"
    assert body["network"]["fact_pagerank"] is not None
    assert body["posts"][0]["first_seen_at"]
    first_seen = body["posts"][0]["first_seen_at"]

    analytics = client.get(f"/api/v1/cases/{case_id}/analytics", headers=auth()).json()
    beta = next(row for row in analytics["network"]["nodes"] if row["handle"] == "beta")
    assert beta["bridge_candidate"] is True
    assert beta["bridge_evidence_classes"] == ["fact"]
    assert analytics["network"]["communities"]
    assert analytics["network"]["metrics"]["cascade_depth"]["status"].startswith("unavailable")

    found = client.get(f"/api/v1/cases/{case_id}/search?q=Bridge", headers=auth())
    assert found.status_code == 200
    assert any(group["type"] == "posts" for group in found.json()["groups"])
    wildcard = client.get(f"/api/v1/cases/{case_id}/search", headers=auth(), params={"q": "%%"})
    assert wildcard.status_code == 200
    assert wildcard.json()["total"] == 0

    replay = _upload_bundle(client, auth, case_id, bundle, expected=200)
    assert replay.json()["replayed"] is True
    reloaded = client.get(f"/api/v1/cases/{case_id}/accounts/{account_id}", headers=auth()).json()
    assert reloaded["summary"]["post_count"] == 3
    assert reloaded["posts"][0]["first_seen_at"] == first_seen
