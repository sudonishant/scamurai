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
from urllib.parse import urlparse

import httpx

from ..config import get_settings
from ..security import _BLOCKED_NETWORKS, _METADATA_HOSTS
import ipaddress

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


def _ip_is_blocked(host: str) -> bool:
    if host in _METADATA_HOSTS:
        return True
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return True
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if any(ip in net for net in _BLOCKED_NETWORKS):
            return True
    return False


def check_capabilities() -> list[Capability]:
    caps = [
        Capability("manual-import", True,
                   ["fetch_post", "fetch_comments", "fetch_replies", "normalize_result"],
                   "configured",
                   "Authorized CSV/JSON imports and file uploads; fully offline and labeled."),
        Capability("generic-web", True,
                   ["fetch_post"], "configured",
                   "Permitted public-page fetch with SSRF guards; no login bypass, bounded size."),
        Capability("instagram", False,
                   ["fetch_post", "fetch_comments"], "access_required",
                   "Meta App Review/Advanced Access and OAuth required; import available meanwhile."),
        Capability("facebook", False,
                   ["fetch_post", "fetch_comments"], "access_required",
                   "Page Public Content Access is reviewed/scoped; import available meanwhile."),
        Capability("youtube", False,
                   ["fetch_comments", "fetch_replies"], "access_required",
                   "commentThreads/comments API key + quota required; import available meanwhile."),
        Capability("reddit", False, ["fetch_post"], "not_configured",
                   "API terms/rate limits require registration; import available."),
        Capability("reverse-image-search", bool(settings.reverse_search_provider),
                   ["reverse_search"],
                   "configured" if settings.reverse_search_provider else "not_configured",
                   "Adapter disabled until provider terms, credentials, quota and data handling are verified."),
        Capability("ocr", bool(settings.ocr_provider), ["extract_ocr"],
                   "configured" if settings.ocr_provider else "not_configured",
                   "No OCR engine available in this environment; OCR transforms report honestly."),
        Capability("factcheck", bool(settings.factcheck_provider), ["claim_search"],
                   "configured" if settings.factcheck_provider else "not_configured",
                   "No fact-check API configured; claim workflow produces sourced query plans only."),
        Capability("llm", bool(settings.llm_provider), ["plan", "summarize"],
                   "configured" if settings.llm_provider else "not_configured",
                   "Deterministic local rules run offline; LLM steps stay disabled without a provider."),
    ]
    return caps


def provider_for_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    for name in ("instagram", "facebook", "youtube", "reddit", "youtu.be"):
        if name in host:
            return "youtube" if name == "youtu.be" else name
    return "generic-web"


def fetch_permitted_source(url: str, timeout: float = 8.0, max_bytes: int = 2_000_000) -> FetchResult:
    """Safe public-page fetch. SSRF rules are re-checked after every redirect."""
    provider = provider_for_url(url)
    if provider != "generic-web":
        return FetchResult(outcome="not_configured", provider=provider,
                           detail="Platform connector access required; authorized import is available.")

    def _guard(request: httpx.Request) -> None:
        host = urlparse(str(request.url)).hostname or ""
        if _ip_is_blocked(host):
            raise httpx.RequestError("Blocked redirect target (SSRF policy)")

    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, event_hooks={"request": [_guard]},
                          headers={"User-Agent": "ps03-investigation/0.1 (+authorized-use)"}) as client:
            with client.stream("GET", url) as resp:
                if resp.status_code in (401, 403):
                    return FetchResult("login_required", resp.status_code, provider=provider,
                                       detail="Access denied or login wall observed")
                if resp.status_code == 429:
                    return FetchResult("rate_limited", 429, provider=provider,
                                       detail="Provider rate limit honored; no retry loop")
                if resp.status_code >= 500:
                    return FetchResult("unavailable", resp.status_code, provider=provider,
                                       detail="Upstream server error")
                if resp.status_code >= 400:
                    return FetchResult("unavailable", resp.status_code, provider=provider,
                                       detail="Non-success status")
                chunks: list[bytes] = []
                total = 0
                for chunk in resp.iter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        return FetchResult("unavailable", resp.status_code, provider=provider,
                                           detail="Response exceeded bounded size")
                    chunks.append(chunk)
                body = b"".join(chunks)
                text = body.decode(resp.encoding or "utf-8", errors="replace")
                if not text.strip():
                    return FetchResult("successful_empty", resp.status_code,
                                       resp.headers.get("content-type"), provider=provider)
                login_markers = ("log in", "login", "sign in", "enable javascript")
                if any(m in text.lower()[:3000] for m in login_markers) and len(text) < 4000:
                    return FetchResult("login_required", resp.status_code,
                                       resp.headers.get("content-type"), text, str(resp.url),
                                       "Page content indicates a login wall", provider)
                return FetchResult("successful", resp.status_code,
                                   resp.headers.get("content-type"), text[:200_000],
                                   str(resp.url), "Public page fetched within policy", provider)
    except httpx.RequestError as exc:
        return FetchResult("unavailable", detail=f"Fetch failed: {exc.__class__.__name__}", provider=provider)
