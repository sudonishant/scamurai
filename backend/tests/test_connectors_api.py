"""Tests for the live-connector router. Provider calls are monkeypatched so
these tests never touch the network or need real credentials."""
from __future__ import annotations

from app.config import get_settings
from app.routers import connectors as connectors_router
from app.services.providers.factcheck import FactCheckError
from app.services.providers.youtube import YouTubeError, YouTubeResult

settings = get_settings()


def test_capabilities_endpoint(client, auth, make_case):
    case_id = make_case()
    r = client.get(f"/api/v1/cases/{case_id}/capabilities", headers=auth())
    assert r.status_code == 200
    providers = {c["provider"]: c for c in r.json()}
    assert {"youtube", "factcheck", "llm", "reddit"}.issubset(providers)
    assert providers["youtube"]["configured"] is False
    assert providers["youtube"]["status"] == "access_required"


def test_capabilities_reflect_configured_key(client, auth, make_case, monkeypatch):
    monkeypatch.setattr(settings, "youtube_api_key", "key")
    monkeypatch.setattr(settings, "google_factcheck_api_key", "key")
    case_id = make_case()
    r = client.get(f"/api/v1/cases/{case_id}/capabilities", headers=auth())
    providers = {c["provider"]: c for c in r.json()}
    assert providers["youtube"]["configured"] is True
    assert providers["factcheck"]["status"] == "configured"


def test_youtube_import_not_configured_is_honest_502(client, auth, make_case, monkeypatch):
    case_id = make_case()

    def boom(*a, **kw):
        raise YouTubeError("not_configured", "PS03_YOUTUBE_API_KEY is not set")

    monkeypatch.setattr(connectors_router.yt_provider, "fetch_youtube_comments", boom)
    r = client.post(f"/api/v1/cases/{case_id}/connectors/youtube/import",
                    headers=auth(), json={"url": "https://youtu.be/abc12345678"})
    assert r.status_code == 502
    assert "not_configured" in r.json()["detail"]


def test_youtube_import_creates_comments(client, auth, make_case, monkeypatch):
    case_id = make_case()
    result = YouTubeResult(video_id="abc12345678", comments=[
        {"comment_id": "c1", "text": "first", "author": "alice",
         "timestamp": "2026-10-01T10:00:00Z", "timestamp_precision": "minute"},
        {"comment_id": "c2", "text": "second", "author": "bob",
         "timestamp": "2026-10-01T10:01:00Z", "timestamp_precision": "minute",
         "parent_id": "c1"},
    ], pages_fetched=1, quota_units=1, outcome="successful", detail="2 comments")
    monkeypatch.setattr(connectors_router.yt_provider, "fetch_youtube_comments",
                        lambda *a, **kw: result)
    r = client.post(f"/api/v1/cases/{case_id}/connectors/youtube/import",
                    headers=auth(), json={"url": "abc12345678"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["comments_created"] == 2
    assert body["coverage"]["status"] == "partial_list_denominator_not_comparable_or_unknown"

    # Idempotent: same comment ids are not duplicated.
    r2 = client.post(f"/api/v1/cases/{case_id}/connectors/youtube/import",
                     headers=auth(), json={"url": "abc12345678"})
    assert r2.status_code == 201
    assert r2.json()["comments_created"] == 0


def test_youtube_import_requires_analyst_role(client, auth, make_case):
    case_id = make_case(members={"viewer@ps03.local": "viewer"})
    r = client.post(f"/api/v1/cases/{case_id}/connectors/youtube/import",
                    headers=auth("viewer"), json={"url": "abc12345678"})
    assert r.status_code == 403


def test_factcheck_search_success_and_empty_semantics(client, auth, make_case, monkeypatch):
    case_id = make_case(members={"analyst@ps03.local": "analyst"})
    monkeypatch.setattr(connectors_router.fc_provider, "search_factchecks",
                        lambda *a, **kw: [{"claim": "x", "outcome": "False", "source": "boimerna"}])
    r = client.post(f"/api/v1/cases/{case_id}/connectors/factcheck/search",
                    headers=auth("analyst"), json={"query": "moon cheese claim"})
    assert r.status_code == 200
    assert r.json()["matches"][0]["outcome"] == "False"
    assert "not that the claim is false" in r.json()["note"]


def test_factcheck_search_not_configured(client, auth, make_case, monkeypatch):
    case_id = make_case()

    def boom(*a, **kw):
        raise FactCheckError("not_configured", "key missing")

    monkeypatch.setattr(connectors_router.fc_provider, "search_factchecks", boom)
    r = client.post(f"/api/v1/cases/{case_id}/connectors/factcheck/search",
                    headers=auth(), json={"query": "some claim text"})
    assert r.status_code == 502


def test_unknown_case_is_404_not_403(client, auth):
    r = client.get("/api/v1/cases/nope/capabilities", headers=auth())
    assert r.status_code == 404
