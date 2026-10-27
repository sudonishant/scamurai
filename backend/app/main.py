"""Scamurai FastAPI entrypoint.

Run locally:  uvicorn app.main:app --reload
Interactive API docs: /docs  (OpenAPI contract at /openapi.json)
"""
from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from . import __version__
from .config import get_settings
from .database import SessionLocal, init_db
from .models import User
from .routers import (
    accounts,
    agent,
    alerts,
    analytics,
    cases,
    comments,
    connectors,
    exports,
    graph,
    media,
    osint,
    runs,
    search,
)
from .services.jobs import reconcile_orphans

settings = get_settings()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
# httpx/httpcore INFO lines print full URLs — Google API keys travel in the query
# string, so keep those loggers above INFO to prevent credential leakage into logs.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger("scamurai")

SEED_USERS = [
    ("owner@scamurai.local", "Case Owner", "dev-token-owner"),
    ("analyst@scamurai.local", "Analyst", "dev-token-analyst"),
    ("reviewer@scamurai.local", "Reviewer", "dev-token-reviewer"),
    ("viewer@scamurai.local", "Read-only Viewer", "dev-token-viewer"),
]


def seed_users() -> None:
    if not settings.dev_auth_enabled:
        return
    with SessionLocal() as db:
        for email, name, token in SEED_USERS:
            if not db.scalar(select(User).where(User.email == email)):
                db.add(User(email=email, name=name, dev_token=token))
        db.commit()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Scamurai Coordinated Disinformation Detection System",
        version=__version__,
        summary="Evidence-first Maltego-style investigation workspace (import-first build).",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        from fastapi.encoders import jsonable_encoder
        return JSONResponse(status_code=422, content={
            "error": "validation_error", "details": jsonable_encoder(exc.errors()),
            "correlation_id": request.headers.get("x-correlation-id", str(uuid.uuid4()))})

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        correlation = str(uuid.uuid4())
        log.exception("unhandled error %s", correlation)  # full detail server-side only
        return JSONResponse(status_code=500, content={
            "error": "internal_error", "retryable": True,
            "correlation_id": correlation,
            "message": "An internal error occurred; no stack trace is exposed to clients."})

    @app.on_event("startup")
    def _startup():
        # Production schemas are changed only through reviewed Alembic
        # revisions. create_all remains a local/test convenience.
        if settings.environment.strip().lower() not in {"production", "prod"}:
            init_db()
        seed_users()
        reconcile_orphans()
        log.info("Scamurai started (env=%s, db=%s, auth=%s, queue=%s, storage=%s)",
                 settings.environment, settings.database_url.split("///")[-1],
                 "development+oidc" if settings.dev_auth_enabled and settings.oidc_issuer
                 else ("development" if settings.dev_auth_enabled else "oidc"),
                 "celery" if settings.redis_url else "in-process",
                 "s3" if settings.storage_backend == "s3" or settings.s3_endpoint else "local")

    @app.get("/health")
    def health():
        return {"status": "ok", "version": __version__,
                "authentication": {
                    "development_tokens": settings.dev_auth_enabled,
                    "oidc_configured": bool(all((settings.oidc_issuer, settings.oidc_audience,
                                                 settings.oidc_jwks_url))),
                },
                "job_runner": "celery" if settings.redis_url else "in-process",
                "storage_backend": "s3" if settings.storage_backend == "s3" or settings.s3_endpoint else "local",
                "providers": {"ocr": settings.ocr_provider, "reverse_search": settings.reverse_search_provider,
                              "factcheck": settings.factcheck_provider, "llm": settings.llm_provider}}

    @app.get("/api/v1/registry")
    def registry():
        from .registry import RELATIONSHIPS, TRANSFORMS
        return {
            "relationships": {k: {"source_types": sorted(v.source_types),
                                  "target_types": sorted(v.target_types),
                                  "derivation_class": v.derivation_class,
                                  "description": v.description} for k, v in RELATIONSHIPS.items()},
            "transforms": {k: {"applies_to": sorted(v.applies_to), "summary": v.summary,
                               "needs_external": v.needs_external} for k, v in TRANSFORMS.items()},
        }

    app.include_router(cases.router)
    app.include_router(accounts.router)
    app.include_router(search.router)
    app.include_router(alerts.router)
    app.include_router(runs.router)
    app.include_router(agent.router)
    app.include_router(graph.router)
    app.include_router(comments.router)
    app.include_router(connectors.router)
    app.include_router(osint.router)
    app.include_router(analytics.router)
    app.include_router(media.router)
    app.include_router(exports.router)
    return app


app = create_app()
