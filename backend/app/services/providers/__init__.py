"""External provider adapters.

Each adapter follows the platform's current API contract (verified Oct 2026)
and fails honestly: missing credentials produce a typed 'not_configured'
result rather than fabricated data. Credentials are read from settings only,
never from prompts, logs, exports or frontend bundles.
"""
from .llm import LLMUnavailable, chat_json, llm_status
from .youtube import fetch_youtube_comments, youtube_status
from .factcheck import search_factchecks, factcheck_status
from .reddit import reddit_status

__all__ = [
    "LLMUnavailable", "chat_json", "llm_status",
    "fetch_youtube_comments", "youtube_status",
    "search_factchecks", "factcheck_status",
    "reddit_status",
]
