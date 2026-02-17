from __future__ import annotations

import hashlib
from urllib.parse import parse_qs, quote, urldefrag, urlsplit

SURF_GO_PATH = "/__web2ru__/go"
SURF_PAGE_PREFIX = "/__web2ru__/page"


def canonicalize_source_url(url: str) -> str:
    cleaned = url.strip()
    no_fragment, _ = urldefrag(cleaned)
    parsed = urlsplit(no_fragment)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"unsupported URL scheme: {parsed.scheme or '<empty>'}")
    if not parsed.hostname:
        raise ValueError("URL hostname is required")
    return no_fragment


def page_key_for_url(url: str) -> str:
    canonical = canonicalize_source_url(url)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def build_go_route(url: str) -> str:
    return f"{SURF_GO_PATH}?url={quote(url, safe='')}"


def parse_go_query(query: str) -> str | None:
    values = parse_qs(query).get("url")
    if not values:
        return None
    raw = values[0].strip()
    if not raw:
        return None
    return raw


def build_page_route(page_key: str, *, fragment: str | None = None) -> str:
    suffix = f"#{fragment}" if fragment else ""
    return f"{SURF_PAGE_PREFIX}/{page_key}/index.html{suffix}"


def same_origin(url_a: str, url_b: str) -> bool:
    parsed_a = urlsplit(canonicalize_source_url(url_a))
    parsed_b = urlsplit(canonicalize_source_url(url_b))
    return (
        parsed_a.scheme == parsed_b.scheme
        and parsed_a.hostname == parsed_b.hostname
        and _normalized_port(parsed_a.scheme, parsed_a.port)
        == _normalized_port(parsed_b.scheme, parsed_b.port)
    )


def split_fragment(url: str) -> tuple[str, str]:
    base, fragment = urldefrag(url.strip())
    return base, fragment


def _normalized_port(scheme: str, port: int | None) -> int:
    if port is not None:
        return port
    if scheme == "https":
        return 443
    return 80
