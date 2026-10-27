from __future__ import annotations

import json

import pytest
from sqlalchemy import func, select, text

from app.config import get_settings
from app.database import SessionLocal
from app.models import Input, Job, MediaAsset


def _create_case(client, auth, *, title="limit-test", limits=None):
    response = client.post(
        "/api/v1/cases", headers=auth(),
        json={"title": title, "limits": limits or {}},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_case_limits_cannot_exceed_deployment_ceiling(client, auth):
    settings = get_settings()
    case = _create_case(client, auth, limits={
        "max_seed_urls": settings.max_seed_urls + 100,
        "max_depth": settings.max_depth + 100,
        "max_new_entities": settings.max_new_entities + 100,
        "max_source_fetches": settings.max_source_fetches + 100,
        "run_deadline_seconds": settings.run_deadline_seconds + 100,
    })
    assert case["limits"] == {
        "max_seed_urls": settings.max_seed_urls,
        "max_depth": settings.max_depth,
        "max_new_entities": settings.max_new_entities,
        "max_source_fetches": settings.max_source_fetches,
        "run_deadline_seconds": settings.run_deadline_seconds,
    }

    tighter = _create_case(client, auth, title="tight-limits", limits={
        "max_seed_urls": 1,
        "max_depth": 1,
        "max_source_fetches": 0,
    })
    assert tighter["limits"]["max_seed_urls"] == 1
    assert tighter["limits"]["max_depth"] == 1
    assert tighter["limits"]["max_source_fetches"] == 0


def test_case_and_run_limits_reject_invalid_values(client, auth, make_case):
    for limits in ({"max_depth": True}, {"max_seed_urls": -1}, {"unrecognized": 1}):
        response = client.post("/api/v1/cases", headers=auth(),
                               json={"title": "invalid-limits", "limits": limits})
        assert response.status_code == 422, response.text

    case_id = make_case()
    response = client.post(
        f"/api/v1/cases/{case_id}/runs", headers=auth(),
        json={"workflow": "image_matching", "client_idempotency_key": "invalid-run-limit",
              "limits": {"run_deadline_seconds": "12"}},
    )
    assert response.status_code == 422, response.text


def test_legacy_invalid_case_limits_fall_back_to_server_ceiling():
    from app.policies import clamp_run_limits

    settings = get_settings()
    effective = clamp_run_limits(
        {"max_seed_urls": "unlimited", "max_depth": -1, "custom": 5000},
        {"max_seed_urls": settings.max_seed_urls + 100},
        settings,
    )
    assert effective["max_seed_urls"] == settings.max_seed_urls
    assert effective["max_depth"] == settings.max_depth


def test_run_limits_only_tighten_case_and_replay_keeps_original_run_id(client, auth):
    case = _create_case(client, auth, limits={
        "max_seed_urls": 1,
        "max_source_fetches": 2,
        "run_deadline_seconds": 60,
    })
    endpoint = f"/api/v1/cases/{case['id']}/runs"
    payload = {
        "workflow": "image_matching",
        "client_idempotency_key": "same-run-key-0001",
        "limits": {
            "max_seed_urls": 10,
            "max_source_fetches": 1,
            "run_deadline_seconds": 20,
        },
    }
    first = client.post(endpoint, headers=auth(), json=payload)
    assert first.status_code == 202, first.text
    first_body = first.json()

    with SessionLocal() as db:
        job = db.get(Job, first_body["job_id"])
        stored = json.loads(job.parameters)
    assert stored["limits"] == {
        "max_seed_urls": 1,
        "max_depth": get_settings().max_depth,
        "max_new_entities": get_settings().max_new_entities,
        "max_source_fetches": 1,
        "run_deadline_seconds": 20,
    }

    replay = client.post(endpoint, headers=auth(), json=payload)
    assert replay.status_code == 202, replay.text
    assert replay.json()["replayed"] is True
    assert replay.json()["job_id"] == first_body["job_id"]
    assert replay.json()["run_id"] == first_body["run_id"]


def test_zero_run_deadline_is_enforced_at_worker_checkpoint(client, auth):
    from app.models import Case
    from app.services.jobs import JobContext

    case = _create_case(client, auth, title="zero-deadline", limits={
        "run_deadline_seconds": 0,
    })
    with SessionLocal() as db:
        case_row = db.get(Case, case["id"])
        job = Job(case_id=case_row.id, kind="deadline-test",
                  parameters=json.dumps({"limits": {"run_deadline_seconds": 0}}))
        db.add(job)
        db.flush()
        context = JobContext(job, db)
        assert context.limits["run_deadline_seconds"] == 0
        with pytest.raises(TimeoutError, match="Run deadline exceeded"):
            context.checkpoint()


def test_import_run_honors_selected_input_ids_and_fetch_budget(
    client, auth, make_case, monkeypatch, wait_job
):
    from app import security
    from app.services import connectors

    monkeypatch.setattr(security, "assert_public_url", lambda url: url)
    called: list[str] = []

    def fake_fetch(url):
        called.append(url)
        return connectors.FetchResult(outcome="unavailable", detail="test fixture")

    monkeypatch.setattr(connectors, "fetch_permitted_source", fake_fetch)
    case = _create_case(client, auth, title="selected-inputs", limits={
        "max_seed_urls": 3, "max_source_fetches": 1,
    })
    urls = ("https://example.com/selected", "https://example.com/not-selected")
    ids = []
    for url in urls:
        response = client.post(
            f"/api/v1/cases/{case['id']}/inputs", headers=auth(),
            json={"url": url},
        )
        assert response.status_code == 201, response.text
        ids.append(response.json()["id"])

    selected = client.post(
        f"/api/v1/cases/{case['id']}/runs", headers=auth(),
        json={"workflow": "import_pipeline", "input_ids": [ids[1]],
              "client_idempotency_key": "selected-input-run-01"},
    )
    assert selected.status_code == 202, selected.text
    selected_job = wait_job(case["id"], selected.json()["job_id"])
    assert selected_job["counts"]["source_fetch_attempts"] == 1
    assert called == [urls[1]]

    capped = client.post(
        f"/api/v1/cases/{case['id']}/runs", headers=auth(),
        json={"workflow": "import_pipeline", "input_ids": [],
              "client_idempotency_key": "empty-selection-run-01"},
    )
    assert capped.status_code == 202, capped.text
    capped_job = wait_job(case["id"], capped.json()["job_id"])
    assert capped_job["counts"]["source_fetch_attempts"] == 1
    assert len(called) == 2
    assert any("Source fetch limit reached" in item for item in capped_job["limitations"])

    seed_limited_case = _create_case(client, auth, title="seed-limit", limits={
        "max_seed_urls": 1, "max_source_fetches": 3,
    })
    for suffix in ("one", "two"):
        response = client.post(
            f"/api/v1/cases/{seed_limited_case['id']}/inputs", headers=auth(),
            json={"url": f"https://example.com/seed-{suffix}"},
        )
        assert response.status_code == 201, response.text
    seed_run = client.post(
        f"/api/v1/cases/{seed_limited_case['id']}/runs", headers=auth(),
        json={"workflow": "import_pipeline", "input_ids": [],
              "client_idempotency_key": "seed-cap-run-0001"},
    )
    assert seed_run.status_code == 202, seed_run.text
    seed_job = wait_job(seed_limited_case["id"], seed_run.json()["job_id"])
    assert seed_job["counts"]["source_fetch_attempts"] == 1
    assert any("Seed URL limit reached" in item for item in seed_job["limitations"])


def test_graph_path_depth_is_clamped_to_case_policy(client, auth, monkeypatch):
    from app.services import graph as graph_service

    case = _create_case(client, auth, title="depth-policy", limits={"max_depth": 1})
    observed = []
    monkeypatch.setattr(
        graph_service, "shortest_known_evidence_path",
        lambda db, case_id, source_id, target_id, max_depth, max_nodes:
            observed.append(max_depth) or [],
    )
    response = client.post(
        f"/api/v1/cases/{case['id']}/graph/path", headers=auth(),
        json={"source_node_id": "source", "target_node_id": "target",
              "max_depth": 10, "max_nodes": 50},
    )
    assert response.status_code == 200, response.text
    assert observed == [1]


def test_import_worker_caps_new_entities(client, auth, monkeypatch, wait_job):
    from app import security
    from app.services import connectors

    monkeypatch.setattr(security, "assert_public_url", lambda url: url)
    called: list[str] = []

    def successful_fetch(url):
        called.append(url)
        return connectors.FetchResult(
            outcome="successful", text="fixture page", final_url=url,
        )

    monkeypatch.setattr(connectors, "fetch_permitted_source", successful_fetch)
    case = _create_case(client, auth, title="entity-limit", limits={
        "max_seed_urls": 3,
        "max_source_fetches": 3,
        "max_new_entities": 1,
    })
    for suffix in ("first", "second"):
        response = client.post(
            f"/api/v1/cases/{case['id']}/inputs", headers=auth(),
            json={"url": f"https://example.com/entity-{suffix}"},
        )
        assert response.status_code == 201, response.text

    run = client.post(
        f"/api/v1/cases/{case['id']}/runs", headers=auth(),
        json={"workflow": "import_pipeline", "input_ids": [],
              "client_idempotency_key": "new-entity-cap-run"},
    )
    assert run.status_code == 202, run.text
    job = wait_job(case["id"], run.json()["job_id"])
    assert job["counts"]["source_fetch_attempts"] == 1
    assert job["counts"]["new_entities_created"] == 1
    assert len(called) == 1
    assert any("New entity limit reached" in item for item in job["limitations"])


@pytest.mark.parametrize(
    ("limit_name", "limit_message"),
    [
        ("max_seed_urls", "Seed URL limit reached"),
        ("max_source_fetches", "Source fetch limit reached"),
        ("max_new_entities", "New entity limit reached"),
    ],
)
def test_successful_fetches_hit_policy_caps_mark_run_partial(
    client, auth, monkeypatch, wait_job, limit_name, limit_message
):
    from app import security
    from app.services import connectors

    monkeypatch.setattr(security, "assert_public_url", lambda url: url)
    called: list[str] = []

    def successful_fetch(url):
        called.append(url)
        return connectors.FetchResult(
            outcome="successful", text="fixture page", final_url=url,
        )

    monkeypatch.setattr(connectors, "fetch_permitted_source", successful_fetch)
    limits = {
        "max_seed_urls": 3,
        "max_source_fetches": 3,
        "max_new_entities": 3,
    }
    limits[limit_name] = 1
    case = _create_case(client, auth, title=f"successful-{limit_name}", limits=limits)
    for suffix in ("first", "second"):
        response = client.post(
            f"/api/v1/cases/{case['id']}/inputs", headers=auth(),
            json={"url": f"https://example.com/{limit_name}-{suffix}"},
        )
        assert response.status_code == 201, response.text

    run = client.post(
        f"/api/v1/cases/{case['id']}/runs", headers=auth(),
        json={"workflow": "import_pipeline", "input_ids": [],
              "client_idempotency_key": f"successful-{limit_name}-cap"},
    )
    assert run.status_code == 202, run.text
    job = wait_job(case["id"], run.json()["job_id"])

    assert job["outcome"] == "partial"
    assert job["counts"]["sources_fetched"] == 1
    assert job["counts"]["source_fetch_attempts"] == 1
    assert job["counts"]["new_entities_created"] == 1
    assert len(called) == 1
    assert any(limit_message in item for item in job["limitations"])


def test_import_run_rejects_duplicate_or_foreign_input_ids(client, auth, make_case):
    first_case = make_case()
    other_case = make_case()
    created = client.post(
        f"/api/v1/cases/{first_case}/inputs", headers=auth(),
        json={"text": "A local-only test input"},
    )
    foreign = client.post(
        f"/api/v1/cases/{other_case}/inputs", headers=auth(),
        json={"text": "A separate case input"},
    )
    assert created.status_code == 201
    assert foreign.status_code == 201
    url = f"/api/v1/cases/{first_case}/runs"
    base = {"workflow": "import_pipeline", "client_idempotency_key": "input-scope-test-01"}
    duplicate = client.post(url, headers=auth(),
                            json={**base, "input_ids": [created.json()["id"], created.json()["id"]]})
    assert duplicate.status_code == 422
    cross_case = client.post(url, headers=auth(),
                             json={**base, "input_ids": [foreign.json()["id"]]})
    assert cross_case.status_code == 422
    missing = client.post(url, headers=auth(), json={**base, "input_ids": ["not-a-real-input"]})
    assert missing.status_code == 422


def test_identical_upload_retry_replays_without_duplicate_media(
    client, auth, make_case, image_dir
):
    case_id = make_case()
    image = (image_dir / "scene_a.png").read_bytes()

    first = client.post(
        f"/api/v1/cases/{case_id}/uploads", headers=auth(),
        files={"file": ("scene_a.png", image, "image/png")},
        data={"kind": "image", "meta": "{}"},
    )
    retry = client.post(
        f"/api/v1/cases/{case_id}/uploads", headers=auth(),
        files={"file": ("scene_a.png", image, "image/png")},
        data={"kind": "image", "meta": "{}"},
    )
    assert first.status_code == 201, first.text
    assert retry.status_code == 201, retry.text
    assert retry.json()["id"] == first.json()["id"]

    renamed = client.post(
        f"/api/v1/cases/{case_id}/uploads", headers=auth(),
        files={"file": ("renamed-copy.png", image, "image/png")},
        data={"kind": "image", "meta": "{}"},
    )
    assert renamed.status_code == 201, renamed.text
    assert renamed.json()["id"] != first.json()["id"]

    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Input).where(Input.case_id == case_id)) == 2
        assert db.scalar(select(func.count()).select_from(MediaAsset).where(MediaAsset.case_id == case_id)) == 2
        keys = db.scalars(select(Input.idempotency_key).where(Input.case_id == case_id)).all()
        assert all(len(key) <= 200 for key in keys)


def test_schema_revision_is_present_after_migration(client):
    with SessionLocal() as db:
        revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert revision == "f8057024479a"
