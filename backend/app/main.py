"""PS-03 FastAPI entrypoint.

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
from .routers import agent, cases, comments, exports, graph, runs
from .services.jobs import reconcile_orphans

settings = get_settings()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("ps03")

SEED_USERS = [
    ("owner@ps03.local", "Case Owner", "dev-token-owner"),
    ("analyst@ps03.local", "Analyst", "dev-token-analyst"),
    ("reviewer@ps03.local", "Reviewer", "dev-token-reviewer"),
    ("viewer@ps03.local", "Read-only Viewer", "dev-token-viewer"),
]


def seed_users() -> None:
    with SessionLocal() as db:
        for email, name, token in SEED_USERS:
            if not db.scalar(select(User).where(User.email == email)):
                db.add(User(email=email, name=name, dev_token=token))
        db.commit()


def create_app() -> FastAPI:
    app = FastAPI(
        title="PS-03 Coordinated Disinformation Detection System",
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
        init_db()
        seed_users()
        reconcile_orphans()
        log.info("PS-03 started (env=%s, db=%s, ocr=%s, reverse=%s, llm=%s)",
                 settings.environment, settings.database_url.split("///")[-1],
                 settings.ocr_provider or "off", settings.reverse_search_provider or "off",
                 settings.llm_provider or "off")

    @app.get("/health")
    def health():
        return {"status": "ok", "version": __version__,
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
    app.include_router(runs.router)
    app.include_router(agent.router)
    app.include_router(graph.router)
    app.include_router(comments.router)
    app.include_router(exports.router)
    return app


app = create_app()
