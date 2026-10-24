"""Regression coverage for real OSINT, analytics, geo and media-forensics upgrades."""
from __future__ import annotations

import json

from app.services import osint as osint_svc
from app.security import ip_is_blocked


def test_non_global_ip_ranges_are_blocked():
    assert ip_is_blocked("100.64.0.1")
    assert ip_is_blocked("198.18.0.1")
    assert ip_is_blocked("::ffff:127.0.0.1")
    assert not ip_is_blocked("8.8.8.8")


def test_target_normalization_uses_psl_and_strips_tracking():
    target = osint_svc.normalize_target("https://www.example.co.uk/path?utm_source=x#fragment")
    assert target.host == "www.example.co.uk"
    assert target.registrable_domain == "example.co.uk"
    assert target.url == "https://www.example.co.uk/path"


def test_investigation_preserves_source_failure(monkeypatch):
    def ok(target):
        return "successful", {"records": [{"type": "A", "data": "93.184.216.34"}]}

    def limited(target):
        raise osint_svc.SourceError("rate_limited", "quota respected", 429)

    monkeypatch.setitem(osint_svc.COLLECTORS, "dns", ok)
    monkeypatch.setitem(osint_svc.COLLECTORS, "rdap", limited)
    report = osint_svc.investigate("example.com", ["dns", "rdap"])
    assert report["status"] == "partial"
    assert report["summary"] == {"sources_succeeded": 1, "sources_total": 2, "sources_limited": 1}
    assert report["modules"][1]["status"] == "rate_limited"
    assert report["modules"][1]["data"] is None


def test_osint_api_persists_real_supplied_report(client, auth, make_case, monkeypatch):
    case_id = make_case()

    def fake_investigation(target, modules):
        return {
            "schema_version": "scamurai-osint-v1", "target": target,
            "normalized_target": "https://example.com/", "target_type": "domain",
            "host": "example.com", "registrable_domain": "example.com", "status": "complete",
            "generated_at": "2026-10-24T00:00:00+00:00",
            "modules": [{"module": "dns", "status": "successful", "data": {"records": []},
                         "error": None, "collected_at": "2026-10-24T00:00:00+00:00"}],
            "summary": {"sources_succeeded": 1, "sources_total": 1, "sources_limited": 0},
            "limitations": ["test limitation"],
        }

    monkeypatch.setattr("app.routers.osint.investigate", fake_investigation)
    response = client.post(f"/api/v1/cases/{case_id}/osint/investigate", headers=auth(),
                           json={"target": "example.com", "modules": ["dns"]})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "complete"
    assert body["evidence_id"]
    reports = client.get(f"/api/v1/cases/{case_id}/osint/reports", headers=auth())
    assert reports.status_code == 200
    assert reports.json()[0]["id"] == body["id"]
    download = client.get(f"/api/v1/cases/{case_id}/osint/reports/{body['id']}/download", headers=auth())
    assert download.status_code == 200
    assert download.headers["x-content-sha256"]


def _campaign_bundle():
    accounts = [{"handle": handle, "platform_id": handle, "profile_url": f"https://example.social/{handle}"}
                for handle in ("alpha", "beta", "gamma")]
    times = ["00:05", "01:05", "02:05", "03:01", "03:02", "03:03"]
    handles = ["alpha", "beta", "alpha", "alpha", "beta", "gamma"]
    posts = []
    for index, (time, handle) in enumerate(zip(times, handles)):
        posts.append({
            "source_id": f"p-{index}", "account_handle": handle,
            "url": f"https://example.social/{handle}/status/{index}",
            "text": "Bridge closed tonight share this urgent public safety update",
            "language": "en", "timestamp": f"2026-10-20T{time}:00+00:00",
            "timestamp_precision": "minute", "collection_status": "authorized_test_import",
            "location": {"name": "Darbhanga", "latitude": 26.1542, "longitude": 85.8918,
                         "precision": "city_reported"},
        })
    return {"platform": "example-social", "accounts": accounts, "posts": posts}


def test_analytics_geo_and_warning_rules(client, auth, make_case):
    case_id = make_case()
    raw = json.dumps(_campaign_bundle()).encode()
    response = client.post(f"/api/v1/cases/{case_id}/uploads", headers=auth(),
                           files={"file": ("campaign.json", raw, "application/json")},
                           data={"kind": "json", "meta": "{}"})
    assert response.status_code == 201, response.text
    analytics = client.get(f"/api/v1/cases/{case_id}/analytics", headers=auth())
    assert analytics.status_code == 200, analytics.text
    body = analytics.json()
    assert body["coverage"]["posts"] == 6
    assert body["coverage"]["geolocated_posts"] == 6
    assert body["narratives"][0]["account_count"] == 3
    assert body["narratives"][0]["earliest_observed"]["handle"] == "alpha"
    assert body["narratives"][0]["early_warning"]["latest_count"] == 3
    assert body["geospatial"]["points"][0]["label"] == "Darbhanga"
    assert body["geospatial"]["anomalies"]
    assert {a["type"] for a in body["alerts"]} >= {"narrative_acceleration", "geospatial_spike"}
    for account in body["automation"]:
        assert account["score_type"] == "transparent_heuristic_not_bot_probability"
        assert "formula" in account


def test_media_forensics_has_no_invented_model_score(client, auth, make_case, upload_file,
                                                     image_dir, run_workflow):
    case_id = make_case()
    upload_file(case_id, next(image_dir.glob("*.png")), "image")
    job = run_workflow(case_id, "media_forensics", "media-forensics-test")
    assert job["lifecycle"] == "completed", job
    response = client.get(f"/api/v1/cases/{case_id}/media/forensics", headers=auth())
    assert response.status_code == 200
    rows = response.json()
    assert rows
    assert rows[0]["model_result"]["status"] == "not_configured"
    assert rows[0]["model_result"]["synthetic_score"] is None
    assert "residual_statistics" in rows[0]["indicators"]["pixels"]


def test_mastodon_import_uses_supplied_public_api_result(client, auth, make_case, monkeypatch):
    case_id = make_case()
    bundle = _campaign_bundle()
    raw = json.dumps([{"id": "public-status"}])

    def fake_fetch(instance, hashtag, limit):
        return {"instance": "example.social", "hashtag": hashtag, "source_url": "https://example.social/api/v1/timelines/tag/test",
                "raw": raw, "statuses_returned": 6, "skipped_reblogs": 0, "bundle": bundle,
                "documentation": "https://docs.joinmastodon.org/methods/timelines/",
                "coverage_note": "bounded test page"}

    monkeypatch.setattr("app.routers.connectors.mastodon_provider.fetch_public_hashtag", fake_fetch)
    response = client.post(f"/api/v1/cases/{case_id}/connectors/mastodon/import", headers=auth(),
                           json={"instance": "example.social", "hashtag": "test", "limit": 40})
    assert response.status_code == 201, response.text
    assert response.json()["posts"] == 6
    assert response.json()["geo_observations"] == 6
    assert response.json()["evidence_id"]
