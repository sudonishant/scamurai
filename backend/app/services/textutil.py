"""Text utilities shared by comment analysis and coordination detection.

Original text is always preserved on the record; these normalized forms live
in separate columns and are never displayed as the source content.
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "mc_eid", "igshid", "ref", "ref_src", "spm")
_PUNCT_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)
_SPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text).lower()
    text = _PUNCT_RE.sub(" ", text)
    return _SPACE_RE.sub(" ", text).strip()


def normalize_url(url: str) -> str:
    """Conservatively strip tracking params; content-identifying params stay."""
    parts = urlsplit(url.strip())
    kept = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if not any(k.lower().startswith(p) for p in _TRACKING_PREFIXES)]
    query = urlencode(kept, doseq=True)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), query, ""))


def split_sentences(text: str) -> list[tuple[int, int, str]]:
    """Return (start, end, sentence) spans, preserving offsets in the source.

    Splits on sentence punctuation including semicolons/pipe, which often
    separate distinct propositions inside a single social post.
    """
    spans: list[tuple[int, int, str]] = []
    cursor = 0
    for match in re.finditer(r"[^.!?।;|]+(?:[.!?।;|]|$)", text):
        sentence = match.group(0).strip()
        if not sentence:
            continue
        start = text.find(sentence, cursor)
        if start < 0:
            continue
        spans.append((start, start + len(sentence), sentence))
        cursor = start + len(sentence)
    return spans
