"""Media forensics route error handling and case isolation.

Regression coverage for the previously untested 404 branch in
``app/routers/media.py``: ``status`` was referenced without being imported, so
the not-found path raised ``NameError`` and returned HTTP 500 instead of 404.
A missing record must be reported honestly, and a record belonging to another
case must never be disclosed.
"""
from __future__ import annotations


def test_unknown_forensics_id_returns_404(client, auth, make_case):
    """A nonexistent forensics id must be an honest 404, never a 500."""
    case_id = make_case()
    r = client.get(f"/api/v1/cases/{case_id}/media/forensics/does-not-exist",
                   headers=auth())
    assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text[:300]}"
    assert r.json()["detail"] == "Media forensics result not found"


def test_forensics_from_another_case_is_not_disclosed(client, auth, make_case,
                                                      upload_file, image_dir,
                                                      run_workflow):
    """Cross-case access must 404 without revealing that the record exists."""
    case_a = make_case("Case A")
    case_b = make_case("Case B")

    upload_file(case_a, next(image_dir.glob("*.png")), "image")
    job = run_workflow(case_a, "media_forensics", "media-cross-case-isolation")
    assert job["lifecycle"] == "completed", job

    rows = client.get(f"/api/v1/cases/{case_a}/media/forensics", headers=auth()).json()
    assert rows, "expected at least one forensics row in case A"
    foreign_id = rows[0]["id"]

    # Owner of case B asking for case A's record: indistinguishable from "missing".
    r = client.get(f"/api/v1/cases/{case_b}/media/forensics/{foreign_id}",
                   headers=auth())
    assert r.status_code == 404, f"cross-case disclosure: {r.status_code} {r.text[:300]}"
    assert r.json()["detail"] == "Media forensics result not found"


def test_forensics_requires_authentication(client, make_case):
    """Unauthenticated access is rejected before the not-found branch runs."""
    case_id = make_case()
    r = client.get(f"/api/v1/cases/{case_id}/media/forensics/anything")
    assert r.status_code in (401, 403), r.text


def test_forensics_list_is_empty_not_error_for_new_case(client, auth, make_case):
    """An empty corpus is a coverage fact, not a failure."""
    case_id = make_case()
    r = client.get(f"/api/v1/cases/{case_id}/media/forensics", headers=auth())
    assert r.status_code == 200
    assert r.json() == []
