"""Reddit Data API status adapter.

Verified Oct 2026: self-service OAuth registration closed under the
Responsible Builder Policy (late 2025); new apps need manual approval
(typically weeks). The free tier is non-commercial, 100 QPM per OAuth
client. This module deliberately exposes status + the approved OAuth flow
helpers rather than pretending access is instant.
"""
from __future__ import annotations

import httpx

from ...config import get_settings

settings = get_settings()
_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"


def reddit_status() -> dict:
    ready = bool(settings.reddit_client_id and settings.reddit_client_secret)
    return {
        "provider": "reddit",
        "configured": ready,
        "operations": ["fetch_post", "fetch_comments"],
        "status": "access_required" if not ready else "configured_pending_approval",
        "detail": (
            "OAuth client registered; Reddit manual app approval is still required for new apps."
            if ready else
            "Register an app at reddit.com/prefs/apps (script type); approval under the "
            "Responsible Builder Policy can take 2-4 weeks and free tier is non-commercial."
        ),
    }


def client_credentials_token(client: httpx.Client | None = None) -> str:
    """OAuth2 client-credentials flow for an approved script app."""
    if not (settings.reddit_client_id and settings.reddit_client_secret):
        raise RuntimeError("not_configured: Reddit OAuth credentials missing")
    owns = client is None
    client = client or httpx.Client(timeout=20.0)
    try:
        resp = client.post(
            _TOKEN_URL,
            auth=(settings.reddit_client_id, settings.reddit_client_secret),
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": settings.reddit_user_agent
                     or "python:ps03-investigation:v0.1 (by /u/yourusername)"})
        if resp.status_code != 200:
            raise RuntimeError(f"reddit token error {resp.status_code}: {resp.text[:200]}")
        return resp.json()["access_token"]
    finally:
        if owns:
            client.close()
