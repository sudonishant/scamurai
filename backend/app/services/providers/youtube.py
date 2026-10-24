"""YouTube Data API v3 connector (public comments, API-key auth).

Verified Oct 2026: commentThreads.list costs 1 quota unit, returns up to 100
threads per page, works with a free API key for public videos, and a default
project gets 10,000 general units/day (plus separate search/upload buckets).
Pagination is bounded by the case policy; every access outcome is recorded
honestly (commentsDisabled, quotaExceeded, login/permission failures).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import httpx

from ...config import get_settings

settings = get_settings()
_API = "https://www.googleapis.com/youtube/v3/commentThreads"
_VIDEO_ID_RE = re.compile(
    r"(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})")


class YouTubeError(RuntimeError):
    def __init__(self, outcome: str, detail: str):
        super().__init__(detail)
        self.outcome = outcome
        self.detail = detail


def youtube_status() -> dict:
    return {
        "provider": "youtube",
        "configured": bool(settings.youtube_api_key),
        "operations": ["fetch_comments", "fetch_replies"],
        "status": "configured" if settings.youtube_api_key else "access_required",
        "detail": ("Free API key, ~10k quota units/day, commentThreads=1 unit/page"
                   if settings.youtube_api_key
                   else "Create a Google Cloud project, enable YouTube Data API v3, create an API key."),
    }


def parse_video_id(url_or_id: str) -> str | None:
    text = url_or_id.strip()
    match = _VIDEO_ID_RE.search(text)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", text):
        return text
    return None


@dataclass
class YouTubeResult:
    video_id: str
    comments: list[dict] = field(default_factory=list)
    pages_fetched: int = 0
    quota_units: int = 0
    outcome: str = "successful"
    detail: str = ""
    next_page_token: str | None = None


def fetch_youtube_comments(url_or_id: str, *, max_pages: int = 5,
                           page_size: int = 100, order: str = "time",
                           client: httpx.Client | None = None) -> YouTubeResult:
    """Fetch bounded public comment threads. A caller-supplied client enables
    deterministic tests via httpx.MockTransport; production uses a default client."""
    if not settings.youtube_api_key:
        raise YouTubeError("not_configured", "SCAMURAI_YOUTUBE_API_KEY is not set")
    video_id = parse_video_id(url_or_id)
    if not video_id:
        raise YouTubeError("validation_error", "Could not parse an 11-character video id")

    owns = client is None
    client = client or httpx.Client(timeout=20.0)
    result = YouTubeResult(video_id=video_id)
    page_token: str | None = None
    try:
        for _ in range(max(1, max_pages)):
            params = {
                "part": "snippet,replies", "videoId": video_id,
                "maxResults": min(page_size, 100), "order": order,
                "key": settings.youtube_api_key,
            }
            if page_token:
                params["pageToken"] = page_token
            try:
                resp = client.get(_API, params=params)
            except httpx.HTTPError as exc:  # connect error, timeout, DNS…
                raise YouTubeError("unavailable",
                                   f"YouTube API transport failure: {type(exc).__name__}")
            if resp.status_code == 403:
                reason = resp.json().get("error", {}).get("errors", [{}])[0].get("reason", "")
                outcome = ("rate_limited" if reason == "quotaExceeded"
                           else "permission_denied")
                raise YouTubeError(outcome, f"403 {reason or 'forbidden'}")
            if resp.status_code == 404:
                raise YouTubeError("unavailable", "video not found or private")
            if resp.status_code == 429:
                raise YouTubeError("rate_limited", "YouTube rate limit honored")
            if resp.status_code >= 400:
                raise YouTubeError("unavailable", f"YouTube API HTTP {resp.status_code}")
            body = resp.json()
            result.pages_fetched += 1
            result.quota_units += 1
            for item in body.get("items", []):
                snippet = item["snippet"]["topLevelComment"]["snippet"]
                result.comments.append({
                    "comment_id": item["id"],
                    "text": snippet.get("textDisplay", ""),
                    "author": snippet.get("authorDisplayName", "unknown"),
                    "timestamp": snippet.get("publishedAt"),
                    "timestamp_precision": "minute",
                    "permalink": item["snippet"]["topLevelComment"].get("id") and
                    f"https://www.youtube.com/watch?v={video_id}&lc={item['id']}",
                    "permalink_status": "available",
                })
                # Replies arrive embedded; preserve hierarchy with stable parent ids.
                for reply in item.get("replies", {}).get("comments", []):
                    rs = reply["snippet"]
                    result.comments.append({
                        "comment_id": reply["id"], "text": rs.get("textDisplay", ""),
                        "author": rs.get("authorDisplayName", "unknown"),
                        "timestamp": rs.get("publishedAt"), "timestamp_precision": "minute",
                        "parent_id": item["id"],
                        "permalink": f"https://www.youtube.com/watch?v={video_id}&lc={reply['id']}",
                        "permalink_status": "available",
                    })
            page_token = body.get("nextPageToken")
            if not page_token:
                break
        result.next_page_token = page_token
        result.outcome = "successful" if result.comments else "successful_empty"
        result.detail = f"{len(result.comments)} comments over {result.pages_fetched} page(s)"
        return result
    finally:
        if owns:
            client.close()
