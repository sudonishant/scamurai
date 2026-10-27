"""External provider adapters.

Each adapter follows the platform's current API contract (verified Oct 2026)
and fails honestly: missing credentials produce a typed 'not_configured'
result rather than fabricated data. Credentials are read from settings only,
never from prompts, logs, exports or frontend bundles.
"""
from .factcheck import factcheck_status, search_factchecks
from .llm import LLMUnavailable, chat_json, llm_status
from .reddit import reddit_status
from .youtube import fetch_youtube_comments, youtube_status

__all__ = [
    "LLMUnavailable",
    "chat_json",
    "factcheck_status",
    "fetch_youtube_comments",
    "llm_status",
    "reddit_status",
    "search_factchecks",
    "youtube_status",
]
