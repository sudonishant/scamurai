"""Public Telegram channel OSINT scraper (zero API keys required).

Ingests public messages directly from Telegram's web preview interface (t.me/s/<channel>).
Extracts message text, timestamps, post IDs, views, forward trails, and embedded media.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

from ..osint import extract_iocs_from_text


class TelegramError(RuntimeError):
    def __init__(self, outcome: str, detail: str):
        super().__init__(detail)
        self.outcome = outcome
        self.detail = detail


def clean_channel_name(target: str) -> str:
    target = target.strip()
    if target.startswith("@"):
        return target[1:]
    if "t.me/" in target:
        path = urlparse(target).path.strip("/")
        if path.startswith("s/"):
            path = path[2:]
        return path.split("/")[0]
    return target


class TelegramHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.messages: list[dict] = []
        self.current_msg: dict | None = None
        self.in_text = False
        self.text_parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        classes = attrs_dict.get("class", "").split()

        if "tgme_widget_message" in classes:
            data_post = attrs_dict.get("data-post", "")
            self.current_msg = {
                "post_id": data_post,
                "url": f"https://t.me/{data_post}" if data_post else None,
                "text": "",
                "timestamp": None,
                "views": None,
                "forwarded_from": None,
                "media_urls": [],
            }
            self.text_parts = []

        if self.current_msg is not None:
            if "tgme_widget_message_text" in classes:
                self.in_text = True
            if tag == "time" and "datetime" in attrs_dict:
                self.current_msg["timestamp"] = attrs_dict["datetime"]
            if "tgme_widget_message_views" in classes:
                self.current_msg["views"] = attrs_dict.get("title")
            if "tgme_widget_message_photo_wrap" in classes:
                style = attrs_dict.get("style", "")
                url_match = re.search(r"url\('([^']+)'\)", style)
                if url_match:
                    self.current_msg["media_urls"].append(url_match.group(1))

    def handle_endtag(self, tag):
        if self.in_text and tag in ("div", "span", "p"):
            self.in_text = False
            if self.current_msg is not None:
                self.current_msg["text"] = " ".join("".join(self.text_parts).split())
        if tag == "div" and self.current_msg is not None and self.current_msg.get("post_id"):
            # Check if this closes message wrap
            pass

    def handle_data(self, data):
        if self.in_text:
            self.text_parts.append(data)


def parse_telegram_preview_html(html_text: str, channel: str) -> list[dict]:
    # Extract messages using robust pattern regex and HTML parser fallback
    parser = TelegramHTMLParser()
    try:
        parser.feed(html_text)
    except Exception:
        pass

    results = []
    # Pattern-based extraction fallback for high reliability
    post_blocks = re.findall(r'<div class="[^"]*tgme_widget_message[^"]*"[^>]*data-post="([^"]+)"(.*?)<div class="tgme_widget_message_footer', html_text, re.DOTALL)

    if post_blocks:
        for post_id, block in post_blocks:
            # Text
            text_match = re.search(r'<div class="[^"]*tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', block, re.DOTALL)
            raw_html = text_match.group(1) if text_match else ""
            clean_text = re.sub(r'<br\s*/?>', ' ', raw_html)
            clean_text = re.sub(r'<[^>]+>', '', clean_text).strip()

            # Time
            time_match = re.search(r'<time[^>]*datetime="([^"]+)"', block)
            dt_str = time_match.group(1) if time_match else None

            # Views
            views_match = re.search(r'<span class="tgme_widget_message_views">([^<]+)</span>', block)
            views_str = views_match.group(1).strip() if views_match else None

            # Forwards
            fwd_match = re.search(r'<a class="tgme_widget_message_forwarded_from_name"[^>]*>([^<]+)</a>', block)
            fwd_from = fwd_match.group(1).strip() if fwd_match else None

            results.append({
                "post_id": post_id,
                "url": f"https://t.me/{post_id}",
                "text": clean_text,
                "timestamp": dt_str,
                "views": views_str,
                "forwarded_from": fwd_from,
            })
    elif parser.messages:
        results = [m for m in parser.messages if m.get("text")]

    return results


def fetch_public_channel(channel: str, limit: int = 50) -> dict:
    channel = clean_channel_name(channel)
    if not channel or not re.match(r"^[a-zA-Z0-9_]{4,64}$", channel):
        raise TelegramError("invalid_channel", f"Invalid Telegram public channel handle: {channel}")

    url = f"https://t.me/s/{channel}"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 404:
                raise TelegramError("channel_not_found", f"Channel @{channel} was not found on Telegram.")
            if resp.status_code != 200:
                raise TelegramError("transport_failure", f"Telegram returned HTTP {resp.status_code}")
            html_text = resp.text
    except httpx.RequestError as exc:
        raise TelegramError("network_unreachable", f"Failed to connect to Telegram: {type(exc).__name__}") from exc

    raw_posts = parse_telegram_preview_html(html_text, channel)
    selected = raw_posts[-limit:]

    # Build importer-compatible case bundle
    posts_bundle = []
    accounts_bundle = [{
        "id": f"tg:{channel}",
        "handle": f"@{channel}",
        "platform": "telegram",
        "url": f"https://t.me/{channel}",
        "metadata": {"source": "telegram_public_preview", "channel": channel}
    }]

    for p in selected:
        text = p["text"]
        iocs = extract_iocs_from_text(text)
        posts_bundle.append({
            "id": f"tg:{p['post_id']}",
            "account_id": f"tg:{channel}",
            "raw_text": text,
            "url": p["url"],
            "timestamp": p["timestamp"],
            "platform": "telegram",
            "metadata": {
                "views": p["views"],
                "forwarded_from": p["forwarded_from"],
                "extracted_iocs": iocs,
            }
        })

    return {
        "channel": channel,
        "source_url": url,
        "posts_count": len(posts_bundle),
        "bundle": {
            "accounts": accounts_bundle,
            "posts": posts_bundle,
            "comments": [],
            "media": []
        }
    }
