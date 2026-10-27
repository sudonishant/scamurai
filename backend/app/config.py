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

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCAMURAI_", env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite:///./scamurai_dev.db"
    # When set, the worker switches from in-process runner to Celery broker config.
    redis_url: str | None = None
    storage_backend: str = "local"  # local | s3
    s3_endpoint: str | None = None
    s3_bucket: str = "scamurai-private"
    s3_region: str = "us-east-1"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_force_path_style: bool = True
    storage_dir: str = str(Path(__file__).resolve().parents[2] / "var" / "storage")

    # Local development tokens are convenient only outside production. When
    # disabled, a fully configured OIDC issuer/JWKS/audience is mandatory.
    dev_auth_enabled: bool = True
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    oidc_algorithms: str = "RS256"
    oidc_leeway_seconds: int = 60
    oidc_timeout_seconds: int = 10

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
    # Optional local Hugging Face image classifier. Empty means no synthetic-media
    # score is produced; deterministic metadata/forensic indicators still run.
    deepfake_model_id: str | None = None
    deepfake_model_revision: str | None = None

    # Bounded passive OSINT sources. No port scanning or credential discovery.
    osint_timeout_seconds: float = 12.0
    osint_max_hostnames: int = 150

    # --- Provider credentials (server-side only; never logged, prompted or exported) ---
    # OpenAI-compatible providers (Groq, OpenRouter): same chat-completions shape.
    llm_api_key: str | None = None
    llm_base_url: str | None = None          # e.g. https://api.groq.com/openai/v1
    gemini_api_key: str | None = None        # Google AI Studio / Gemini API credential
    youtube_api_key: str | None = None       # Google Cloud, YouTube Data API v3
    google_factcheck_api_key: str | None = None
    reddit_client_id: str | None = None      # Official approval/access still required
    reddit_client_secret: str | None = None
    reddit_user_agent: str | None = None
    geo_min_group_size: int = 3

    export_link_ttl_seconds: int = 3600
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @model_validator(mode="after")
    def validate_authentication(self):
        production = self.environment.strip().lower() in {"production", "prod"}
        if production and self.dev_auth_enabled:
            raise ValueError("Development tokens cannot be enabled in production")
        if not self.dev_auth_enabled and not all(
                (self.oidc_issuer, self.oidc_audience, self.oidc_jwks_url)):
            raise ValueError(
                "OIDC_ISSUER, OIDC_AUDIENCE and OIDC_JWKS_URL are required when dev auth is disabled")
        if self.geo_min_group_size < 1:
            raise ValueError("GEO_MIN_GROUP_SIZE must be at least 1")
        if self.storage_backend not in {"local", "s3"}:
            raise ValueError("STORAGE_BACKEND must be 'local' or 's3'")
        if self.storage_backend == "s3" and not self.s3_bucket.strip():
            raise ValueError("S3_BUCKET is required for S3 storage")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def oidc_algorithm_list(self) -> list[str]:
        return [item.strip() for item in self.oidc_algorithms.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    # Remote object storage must not require or mutate a local filesystem.
    # Preserve the legacy endpoint-only S3 configuration in the same way.
    if settings.storage_backend == "local" and not settings.s3_endpoint:
        os.makedirs(settings.storage_dir, exist_ok=True)
    return settings
