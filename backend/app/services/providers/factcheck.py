"""Google Fact Check Tools API adapter (free, API-key auth).

Endpoint verified Oct 2026: GET factchecktools.googleapis.com/v1alpha1/claims:search
A missing result means no matching published fact-check, NOT that the claim is
false — the caller preserves that distinction.
"""
from __future__ import annotations

import httpx

from ...config import get_settings

settings = get_settings()
_ENDPOINT = "https://factchecktools.googleapis.com/v1alpha1/claims:search"


class FactCheckError(RuntimeError):
    def __init__(self, outcome: str, detail: str):
        super().__init__(detail)
        self.outcome = outcome
        self.detail = detail


def factcheck_status() -> dict:
    return {
        "provider": "factcheck",
        "configured": bool(settings.google_factcheck_api_key),
        "operations": ["claim_search"],
        "status": "configured" if settings.google_factcheck_api_key else "not_configured",
        "detail": ("Free Claim Search API with standard quota"
                   if settings.google_factcheck_api_key
                   else "Enable Fact Check Tools API in Google Cloud and create an API key."),
    }


def search_factchecks(query: str, *, language_code: str | None = None,
                      max_age_days: int | None = None,
                      client: httpx.Client | None = None) -> list[dict]:
    if not settings.google_factcheck_api_key:
        raise FactCheckError("not_configured", "PS03_GOOGLE_FACTCHECK_API_KEY is not set")
    params: dict = {"query": query, "key": settings.google_factcheck_api_key, "pageSize": 25}
    if language_code:
        params["languageCode"] = language_code
    if max_age_days:
        params["maxAgeDays"] = max_age_days
    owns = client is None
    client = client or httpx.Client(timeout=20.0)
    try:
        try:
            resp = client.get(_ENDPOINT, params=params)
        except httpx.HTTPError as exc:
            raise FactCheckError("unavailable",
                                 f"Fact Check API transport failure: {type(exc).__name__}")
        if resp.status_code == 429:
            raise FactCheckError("rate_limited", "Fact Check API rate limit")
        if resp.status_code == 403:
            raise FactCheckError("permission_denied", "API not enabled or key restricted")
        if resp.status_code >= 400:
            raise FactCheckError("unavailable", f"Fact Check API HTTP {resp.status_code}")
        body = resp.json()
        return [
            {
                "claim": item.get("text", ""),
                "claimant": item.get("claimant", ""),
                "claim_date": item.get("claimDate"),
                "outcome": (item.get("claimReview", [{}])[0] or {}).get("textualRating", ""),
                "source": (item.get("claimReview", [{}])[0] or {}).get("publisher", {}).get("site", ""),
                "url": (item.get("claimReview", [{}])[0] or {}).get("url", ""),
            }
            for item in body.get("claims", [])
        ]
    finally:
        if owns:
            client.close()
