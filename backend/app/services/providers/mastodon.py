"""Mastodon public hashtag timeline adapter (official instance REST API).

Only public, unauthenticated timeline data is requested. Instances may disable
public preview; 401/403/429 and transport failures remain distinct outcomes.
No private statuses, login bypass or follower enumeration is performed.
"""
from __future__ import annotations

import json
from html.parser import HTMLParser
from urllib.parse import quote, urlparse

from ..connectors import fetch_permitted_source


class MastodonError(RuntimeError):
    def __init__(self, outcome: str, detail: str):
        super().__init__(detail)
        self.outcome = outcome
        self.detail = detail


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        if tag in {"br", "p", "li"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str):
        if tag in {"p", "li"}:
            self.parts.append("\n")

    def handle_data(self, data: str):
        self.parts.append(data)

    def text(self) -> str:
        lines = [" ".join(line.split()) for line in "".join(self.parts).splitlines()]
        return "\n".join(line for line in lines if line).strip()


def plain_text(html: str) -> str:
    parser = TextExtractor()
    parser.feed(html or "")
    return parser.text()


def normalize_instance(value: str) -> str:
    candidate = value.strip() if "://" in value else f"https://{value.strip()}"
    parsed = urlparse(candidate)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise MastodonError("validation_error", "Use an HTTPS Mastodon instance hostname without credentials")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.port not in {None, 443}:
        raise MastodonError("validation_error", "Enter only the instance hostname, not a status URL or nonstandard port")
    host = parsed.hostname.rstrip(".").lower()
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise MastodonError("validation_error", "Invalid instance hostname") from exc
    if "." not in host:
        raise MastodonError("validation_error", "A public instance hostname is required")
    return host


def fetch_public_hashtag(instance: str, hashtag: str, limit: int = 40) -> dict:
    host = normalize_instance(instance)
    tag = hashtag.strip().lstrip("#")
    if not tag or len(tag) > 100 or any(c.isspace() or c in "/?&#" for c in tag):
        raise MastodonError("validation_error", "Hashtag must be 1–100 characters without spaces or URL delimiters")
    url = f"https://{host}/api/v1/timelines/tag/{quote(tag)}?limit={limit}&local=false"
    result = fetch_permitted_source(url, timeout=15, max_bytes=4_000_000,
                                    max_text_chars=4_000_000, detect_login_wall=False)
    if result.outcome != "successful":
        raise MastodonError(result.outcome, result.detail)
    try:
        statuses = json.loads(result.text)
    except json.JSONDecodeError as exc:
        raise MastodonError("unavailable", "Instance returned malformed JSON") from exc
    if not isinstance(statuses, list):
        raise MastodonError("unavailable", "Instance response is not a public status array")

    accounts: dict[str, dict] = {}
    posts = []
    skipped_reblogs = 0
    for status in statuses[:limit]:
        if not isinstance(status, dict):
            continue
        if status.get("reblog"):
            skipped_reblogs += 1
            continue
        if status.get("visibility") != "public":
            continue
        account = status.get("account") or {}
        status_id = str(status.get("id") or "")
        account_id = str(account.get("id") or "")
        if not status_id or not account_id:
            continue
        handle = str(account.get("acct") or account.get("username") or "unknown")
        accounts[handle] = {
            "platform_id": account_id,
            "handle": handle,
            "display_name": str(account.get("display_name") or ""),
            "profile_url": account.get("url"),
            "identity_confirmed": False,
        }
        posts.append({
            "source_id": f"{host}:{status_id}",
            "url": status.get("url") or status.get("uri"),
            "account_handle": handle,
            "text": plain_text(str(status.get("content") or "")),
            "language": status.get("language") or "und",
            "timestamp": status.get("created_at"),
            "timestamp_precision": "second",
            "collection_status": "live_public_api",
        })
    return {
        "instance": host,
        "hashtag": tag,
        "source_url": url,
        "raw": result.text,
        "statuses_returned": len(statuses),
        "skipped_reblogs": skipped_reblogs,
        "bundle": {"platform": f"mastodon:{host}", "accounts": list(accounts.values()), "posts": posts},
        "documentation": "https://docs.joinmastodon.org/methods/timelines/",
        "coverage_note": "One bounded public hashtag page; reblogs and non-public/unlisted statuses are not imported. This is not full platform coverage.",
    }
