"""Versioned connector interface (master prompt section 8).

Every connector declares its capabilities honestly. Not-supported,
login-required, permission-denied, rate-limited, unavailable and
successful-empty are distinct outcomes — never collapsed into
'nothing exists'. Mocks are visibly labeled; no credential ever leaves
the server.
"""
from __future__ import annotations

import socket
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx

from ..config import get_settings
from ..security import _METADATA_HOSTS, ip_is_blocked

settings = get_settings()

OUTCOMES = (
    "successful", "successful_empty", "not_supported", "login_required",
    "permission_denied", "rate_limited", "unavailable", "not_configured",
)


@dataclass
class Capability:
    provider: str
    configured: bool
    operations: list[str]
    status: str
    detail: str

    def as_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class FetchResult:
    outcome: str
    status_code: int | None = None
    content_type: str | None = None
    text: str = ""
    final_url: str | None = None
    detail: str = ""
    provider: str = "generic-web"
    is_mock: bool = False
    access_observations: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)
    redirect_history: list[dict] = field(default_factory=list)


def _ip_is_blocked(host: str) -> bool:
    host = host.rstrip(".").lower()
    if host in _METADATA_HOSTS or host.endswith(".internal") or host == "localhost":
        return True
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return True
    return any(ip_is_blocked(info[4][0]) for info in infos)


def check_capabilities() -> list[Capability]:
    caps = [
        Capability("manual-import", True,
                   ["fetch_post", "fetch_comments", "fetch_replies", "normalize_result"],
                   "configured",
                   "Authorized CSV/JSON imports and file uploads; fully offline and labeled."),
        Capability("generic-web", True,
                   ["fetch_post"], "configured",
                   "Permitted public-page fetch with SSRF guards; no login bypass, bounded size."),
        Capability("public-infrastructure-osint", True,
                   ["dns", "rdap", "web_metadata", "certificate_transparency", "wayback"],
                   "configured",
                   "Keyless bounded public APIs; per-source failures are preserved and reports are hash-snapshotted."),
        Capability("mastodon", True,
                   ["fetch_public_hashtag_timeline"], "configured_public_access_dependent",
                   "Official instance API; public preview can be disabled. One page, no private statuses or login bypass."),
        Capability("media-forensics", True,
                   ["metadata", "jpeg_residuals", "provenance_markers"], "configured",
                   "Deterministic screening observations; not a standalone manipulation verdict."),
        Capability("deepfake-model", bool(settings.deepfake_model_id),
                   ["image_classification"], "configured" if settings.deepfake_model_id else "not_configured",
                   "Raw scores only from the explicitly configured local model; representative calibration is still required."
                   if settings.deepfake_model_id else
                   "No model score is invented. Set SCAMURAI_DEEPFAKE_MODEL_ID and install optional transformers dependencies."),
        Capability("instagram", False,
                   ["fetch_post", "fetch_comments"], "access_required",
                   "Meta App Review/Advanced Access and OAuth required; import available meanwhile."),
        Capability("facebook", False,
                   ["fetch_post", "fetch_comments"], "access_required",
                   "Page Public Content Access is reviewed/scoped; import available meanwhile."),
        Capability("youtube", bool(settings.youtube_api_key),
                   ["fetch_comments", "fetch_replies"],
                   "configured" if settings.youtube_api_key else "access_required",
                   "Free API key; commentThreads=1 quota unit, ~10k units/day."
                   if settings.youtube_api_key else
                   "commentThreads/comments API key + quota required; import available meanwhile."),
        Capability("reddit", bool(settings.reddit_client_id), ["fetch_post"],
                   "configured_pending_approval" if settings.reddit_client_id else "not_configured",
                   ("OAuth client registered; Reddit manual app approval still required (2025 policy)."
                    if settings.reddit_client_id else
                    "Approval-gated since 2025 (2-4 weeks); free tier non-commercial; import available.")),
        Capability("reverse-image-search", bool(settings.reverse_search_provider),
                   ["reverse_search"],
                   "configured" if settings.reverse_search_provider else "not_configured",
                   "Adapter disabled until provider terms, credentials, quota and data handling are verified."),
        Capability("ocr", bool(settings.ocr_provider), ["extract_ocr"],
                   "configured" if settings.ocr_provider else "not_configured",
                   "No OCR engine available in this environment; OCR transforms report honestly."),
        Capability("factcheck", bool(settings.google_factcheck_api_key or settings.factcheck_provider),
                   ["claim_search"],
                   "configured" if (settings.google_factcheck_api_key or settings.factcheck_provider)
                   else "not_configured",
                   ("Google Fact Check Tools API; no result is never proof of falsity."
                    if (settings.google_factcheck_api_key or settings.factcheck_provider) else
                    "No fact-check API configured; claim workflow produces sourced query plans only.")),
        Capability("llm", bool(settings.llm_api_key or settings.gemini_api_key or settings.llm_provider),
                   ["plan", "extract", "summarize"],
                   "configured" if (settings.llm_api_key or settings.gemini_api_key or settings.llm_provider)
                   else "not_configured",
                   "Deterministic local rules run offline; LLM steps activate only with a key."),
    ]
    return caps


def provider_for_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    for name in ("instagram", "facebook", "youtube", "reddit", "youtu.be"):
        if name in host:
            return "youtube" if name == "youtu.be" else name
    return "generic-web"


def fetch_permitted_source(
    url: str,
    timeout: float = 8.0,
    max_bytes: int = 2_000_000,
    max_text_chars: int = 200_000,
    allowed_platform: str | None = None,
    detect_login_wall: bool = True,
) -> FetchResult:
    """Bounded public-page fetch with explicit per-hop policy checks.

    Redirects are handled manually (maximum four) so every target is checked.
    Non-global IPs, credentialed URLs and non-HTTP schemes are rejected. For a
    hostile multi-tenant deployment, add DNS pinning/network egress controls as
    described in SECURITY.md; URL validation alone is not a complete sandbox.
    """
    provider = provider_for_url(url)
    if provider != "generic-web" and provider != allowed_platform:
        return FetchResult(outcome="not_configured", provider=provider,
                           detail="Platform connector access required; authorized import is available.")

    current_url = url
    redirects: list[dict] = []
    try:
        with httpx.Client(
            follow_redirects=False,
            timeout=timeout,
            headers={"User-Agent": "Scamurai/0.2 (+authorized-public-research)"},
        ) as client:
            for hop in range(5):
                parsed = urlparse(current_url)
                host = (parsed.hostname or "").rstrip(".").lower()
                if (parsed.scheme not in {"http", "https"} or not host or parsed.username
                        or parsed.password or _ip_is_blocked(host)):
                    return FetchResult("unavailable", provider=provider,
                                       detail="Blocked non-public or invalid fetch target")
                with client.stream("GET", current_url) as resp:
                    response_headers = {k.lower(): v for k, v in resp.headers.items()
                                        if k.lower() not in {"set-cookie", "authorization"}}
                    if resp.status_code in {301, 302, 303, 307, 308}:
                        location = resp.headers.get("location")
                        if not location or hop >= 4:
                            return FetchResult("unavailable", resp.status_code, provider=provider,
                                               detail="Redirect limit or missing redirect destination")
                        next_url = urljoin(str(resp.url), location)
                        redirects.append({"status": resp.status_code, "from": str(resp.url), "to": next_url})
                        current_url = next_url
                        continue
                    if resp.status_code in (401, 403):
                        return FetchResult("login_required", resp.status_code, provider=provider,
                                           detail="Access denied, robots policy or login wall observed",
                                           headers=response_headers, redirect_history=redirects)
                    if resp.status_code == 429:
                        return FetchResult("rate_limited", 429, provider=provider,
                                           detail="Provider rate limit honored; no retry loop",
                                           headers=response_headers, redirect_history=redirects)
                    if resp.status_code >= 500:
                        return FetchResult("unavailable", resp.status_code, provider=provider,
                                           detail="Upstream server error", headers=response_headers,
                                           redirect_history=redirects)
                    if resp.status_code >= 400:
                        return FetchResult("unavailable", resp.status_code, provider=provider,
                                           detail="Source returned a non-success status",
                                           headers=response_headers, redirect_history=redirects)
                    chunks: list[bytes] = []
                    total = 0
                    for chunk in resp.iter_bytes():
                        total += len(chunk)
                        if total > max_bytes:
                            return FetchResult("unavailable", resp.status_code, provider=provider,
                                               detail="Response exceeded bounded size",
                                               headers=response_headers, redirect_history=redirects)
                        chunks.append(chunk)
                    body = b"".join(chunks)
                    text = body.decode(resp.encoding or "utf-8", errors="replace")
                    common = dict(status_code=resp.status_code,
                                  content_type=resp.headers.get("content-type"),
                                  final_url=str(resp.url), provider=provider,
                                  headers=response_headers, redirect_history=redirects)
                    if not text.strip():
                        return FetchResult("successful_empty", text="", **common)
                    login_markers = ("log in", "login", "sign in", "enable javascript")
                    if detect_login_wall and any(m in text.lower()[:3000] for m in login_markers) and len(text) < 4000:
                        return FetchResult("login_required", text=text[:max_text_chars],
                                           detail="Page content indicates a login wall", **common)
                    return FetchResult("successful", text=text[:max_text_chars],
                                       detail="Public source fetched within policy", **common)
            return FetchResult("unavailable", provider=provider, detail="Redirect processing ended unexpectedly")
    except (httpx.RequestError, httpx.DecodingError) as exc:
        return FetchResult("unavailable", detail=f"Fetch failed: {exc.__class__.__name__}",
                           provider=provider, redirect_history=redirects)
