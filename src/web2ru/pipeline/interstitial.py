from __future__ import annotations

import re

_TITLE_JUST_A_MOMENT_RE = re.compile(r"<title>\s*just a moment", re.IGNORECASE)
_TITLE_ATTENTION_REQUIRED_RE = re.compile(r"<title>\s*attention required", re.IGNORECASE)
_STRONG_MARKERS = (
    "/cdn-cgi/challenge-platform/",
    "challenges.cloudflare.com/turnstile",
    "cf-challenge",
    "cf-error-details",
)
_WEAK_MARKERS = (
    "cloudflare",
    "please enable cookies",
    "ddos protection by cloudflare",
)


def looks_like_access_interstitial(html_text: str) -> bool:
    lowered = html_text.lower()
    if any(marker in lowered for marker in _STRONG_MARKERS):
        return True

    if _TITLE_JUST_A_MOMENT_RE.search(html_text) and any(marker in lowered for marker in _WEAK_MARKERS):
        return True

    return bool(_TITLE_ATTENTION_REQUIRED_RE.search(html_text) and "cloudflare" in lowered)
