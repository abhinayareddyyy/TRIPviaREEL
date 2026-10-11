"""Best-effort retrieval of a public Instagram reel's caption.

Instagram usually blocks anonymous scraping, so failure is the *expected*
outcome and the app falls back to uploads / pasted captions. Only instagram.com
hosts are ever contacted (no arbitrary URL fetching).
"""
from __future__ import annotations

import html
import re
import urllib.error
import urllib.request
from typing import Optional, Tuple
from urllib.parse import urlparse

ALLOWED_HOSTS = {"instagram.com", "www.instagram.com", "m.instagram.com", "instagr.am"}
_PATH_RE = re.compile(r"^/(?:[\w.]+/)?(reel|reels|p|tv)/([\w-]+)/?$")
TIMEOUT_S = 6


class InvalidReelURL(ValueError):
    pass


def validate_reel_url(url: str) -> str:
    url = (url or "").strip()
    parsed = urlparse(url if "://" in url else "https://" + url)
    if parsed.scheme not in ("http", "https") or (parsed.hostname or "").lower() not in ALLOWED_HOSTS:
        raise InvalidReelURL("Please paste an Instagram reel link (instagram.com/reel/...).")
    if not _PATH_RE.match(parsed.path):
        raise InvalidReelURL("That doesn't look like a reel or post link (expected instagram.com/reel/<id>).")
    return f"https://www.instagram.com{parsed.path}"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # never follow redirects (login walls, other hosts)
        return None


def fetch_caption(url: str) -> Tuple[Optional[str], str]:
    """Return (caption_text_or_None, status) where status is 'ok' or 'blocked'."""
    clean = validate_reel_url(url)
    req = urllib.request.Request(clean, headers={"User-Agent": "Mozilla/5.0 (TripViaReel student project)"})
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=TIMEOUT_S) as resp:
            body = resp.read(400_000).decode("utf-8", errors="ignore")
    except (urllib.error.URLError, OSError, ValueError):
        return None, "blocked"
    parts = []
    for prop in ("og:title", "og:description"):
        m = re.search(rf'<meta[^>]+property="{prop}"[^>]+content="([^"]*)"', body)
        if m:
            parts.append(html.unescape(m.group(1)))
    text = "\n".join(parts).strip()
    if not text or "log in" in text.lower()[:80]:
        return None, "blocked"
    return text, "ok"
