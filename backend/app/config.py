"""Runtime configuration.

Local development defaults to SQLite + local-disk storage + an in-process job
runner. The same code runs against PostgreSQL/Redis/S3 via environment
variables (see .env.example and docker-compose.yml). Provider/model IDs live
in configuration only — never hard-coded inside business logic.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# Support both SCAMURAI_ and legacy PS03_ env vars
for _k, _v in list(os.environ.items()):
    if _k.startswith("PS03_"):
        os.environ.setdefault("SCAMURAI_" + _k[5:], _v)
    elif _k.startswith("SCAMURAI_"):
        os.environ.setdefault("PS03_" + _k[9:], _v)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCAMURAI_", env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite:///./scamurai_dev.db"
    # When set, the worker switches from in-process runner to Celery broker config.
    redis_url: str | None = None
    s3_endpoint: str | None = None
    s3_bucket: str = "scamurai-private"
    storage_dir: str = str(Path(__file__).resolve().parents[2] / "var" / "storage")

    # Auth — dev tokens are demo-only and must be replaced by an IdP/OAuth in deployment.
    dev_auth_enabled: bool = True
    jwt_secret: str = "change-me-in-deployment"

    # Prototype guardrails (section 4 of the master prompt); adjustable engineering defaults.
    max_seed_urls: int = 5
    max_depth: int = 2
    max_new_entities: int = 200
    max_source_fetches: int = 20
    run_deadline_seconds: int = 600
    max_upload_bytes: int = 15 * 1024 * 1024
    max_image_pixels: int = 64_000_000

    # Image pipeline
    phash_distance_threshold: int = 5
    pixel_correlation_threshold: float = 0.82

    # Coordination
    coordination_window_minutes: int = 10
    near_duplicate_ratio: float = 0.88

    # External providers — empty means "not configured"; the UI must say so honestly.
    ocr_provider: str | None = None          # e.g. "tesseract" when a binary is available
    reverse_search_provider: str | None = None
    factcheck_provider: str | None = None
    llm_provider: str | None = None          # "groq" | "openrouter" | "gemini"
    llm_model_id: str | None = None
    jev_api_url: str | None = None

    # --- Provider credentials (server-side only; never logged, prompted or exported) ---
    # OpenAI-compatible providers (Groq, OpenRouter): same chat-completions shape.
    llm_api_key: str | None = None
    llm_base_url: str | None = None          # e.g. https://api.groq.com/openai/v1
    gemini_api_key: str | None = None        # aistudio.google.com free-tier key
    youtube_api_key: str | None = None       # Google Cloud, YouTube Data API v3
    google_factcheck_api_key: str | None = None
    reddit_client_id: str | None = None      # reddit.com/prefs/apps (approval-gated since 2025)
    reddit_client_secret: str | None = None
    reddit_user_agent: str | None = None

    export_link_ttl_seconds: int = 3600
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    os.makedirs(settings.storage_dir, exist_ok=True)
    return settings
