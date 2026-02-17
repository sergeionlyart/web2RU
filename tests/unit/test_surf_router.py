from __future__ import annotations

import pytest

from web2ru.surf.router import (
    build_go_route,
    build_page_route,
    canonicalize_source_url,
    parse_go_query,
    same_origin,
    split_fragment,
)


def test_canonicalize_source_url_rejects_non_http_scheme() -> None:
    with pytest.raises(ValueError):
        canonicalize_source_url("file:///tmp/page.html")


def test_same_origin_handles_default_ports() -> None:
    assert same_origin("https://example.com/path", "https://example.com:443/other")
    assert same_origin("http://example.com", "http://example.com:80/docs")
    assert not same_origin("https://example.com", "https://example.org")


def test_go_route_roundtrip_and_page_route_fragment() -> None:
    url = "https://example.com/docs/page#chapter-2"
    route = build_go_route(url)
    assert route.startswith("/__web2ru__/go?url=")
    parsed = parse_go_query(route.split("?", 1)[1])
    assert parsed == url

    base, fragment = split_fragment(url)
    assert base == "https://example.com/docs/page"
    assert fragment == "chapter-2"
    assert build_page_route("abc123", fragment=fragment) == "/__web2ru__/page/abc123/index.html#chapter-2"
