from __future__ import annotations

import threading

from web2ru.assets.cache import AssetCache
from web2ru.assets.fetch_missing import fetch_missing_assets


class _FakeResponse:
    def __init__(
        self,
        *,
        url: str,
        status_code: int,
        content_type: str,
        content: bytes,
    ) -> None:
        self.url = url
        self.status_code = status_code
        self.content = content
        self.headers = {"content-type": content_type}


def _fake_http_client(responses: dict[str, _FakeResponse]) -> type:
    class FakeClient:
        calls: list[str] = []

        def __init__(self, **kwargs: object) -> None:
            return None

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def get(self, url: str) -> _FakeResponse:
            FakeClient.calls.append(url)
            return responses[url]

    return FakeClient


def test_fetch_missing_assets_disabled_marks_all_missing() -> None:
    cache = AssetCache()
    missing = fetch_missing_assets(
        needed_urls={"https://example.com/a.css", "https://example.com/b.js"},
        asset_cache=cache,
        final_url="https://example.com/page",
        user_agent="pytest-agent",
        max_asset_mb=15,
        enabled=False,
    )
    assert len(missing) == 2
    assert {entry.reason for entry in missing} == {"disabled"}


def test_fetch_missing_assets_reuses_single_client_and_fetches_all(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    class FakeResponse:
        def __init__(self, *, url: str, status_code: int, content: bytes) -> None:
            self.url = url
            self.status_code = status_code
            self.content = content
            self.headers = {"content-type": "text/plain"}

    class FakeClient:
        init_count = 0
        calls: list[str] = []
        lock = threading.Lock()

        def __init__(self, **kwargs) -> None:  # noqa: ANN003
            FakeClient.init_count += 1

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001, ANN002, ANN003
            return None

        def get(self, url: str) -> FakeResponse:
            with FakeClient.lock:
                FakeClient.calls.append(url)
            if url.endswith("bad"):
                return FakeResponse(url=url, status_code=404, content=b"")
            return FakeResponse(url=f"{url}?final=1", status_code=200, content=b"ok")

    monkeypatch.setattr("web2ru.assets.fetch_missing.httpx.Client", FakeClient)

    cache = AssetCache()
    urls = {
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/bad",
    }
    missing = fetch_missing_assets(
        needed_urls=urls,
        asset_cache=cache,
        final_url="https://example.com/page",
        user_agent="pytest-agent",
        max_asset_mb=15,
        enabled=True,
    )

    assert FakeClient.init_count == 1
    assert set(FakeClient.calls) == urls
    assert cache.has("https://example.com/a")
    assert cache.has("https://example.com/b")
    assert not cache.has("https://example.com/bad")
    assert len(missing) == 1
    assert missing[0].reason == "http_404"


def test_fetch_missing_assets_uses_next_image_source_after_http_error(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    optimized_url = (
        "https://www.example.com/_next/image?"
        "url=https%3A%2F%2Fcdn.example.com%2Fhero.png&w=3840&q=75"
    )
    source_url = "https://cdn.example.com/hero.png"
    FakeClient = _fake_http_client(
        {
            optimized_url: _FakeResponse(
                url=optimized_url,
                status_code=429,
                content_type="text/html",
                content=b"rate limited",
            ),
            source_url: _FakeResponse(
                url=source_url,
                status_code=200,
                content_type="image/png",
                content=b"png",
            ),
        }
    )

    monkeypatch.setattr("web2ru.assets.fetch_missing.httpx.Client", FakeClient)

    cache = AssetCache()
    missing = fetch_missing_assets(
        needed_urls={optimized_url},
        asset_cache=cache,
        final_url="https://www.example.com/page",
        user_agent="pytest-agent",
        max_asset_mb=15,
        enabled=True,
    )

    record = cache.get(optimized_url)
    assert missing == []
    assert FakeClient.calls == [optimized_url, source_url]
    assert record is not None
    assert record.final_url == source_url
    assert record.content_type == "image/png"
    assert record.data == b"png"


def test_fetch_missing_assets_uses_next_image_source_after_html_payload(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    optimized_url = "https://www.example.com/_next/image?url=%2Fimages%2Fdiagram.jpg&w=1920&q=75"
    source_url = "https://www.example.com/images/diagram.jpg"
    FakeClient = _fake_http_client(
        {
            optimized_url: _FakeResponse(
                url=optimized_url,
                status_code=200,
                content_type="text/html; charset=utf-8",
                content=b"<html></html>",
            ),
            source_url: _FakeResponse(
                url=source_url,
                status_code=200,
                content_type="image/jpeg",
                content=b"jpg",
            ),
        }
    )

    monkeypatch.setattr("web2ru.assets.fetch_missing.httpx.Client", FakeClient)

    cache = AssetCache()
    missing = fetch_missing_assets(
        needed_urls={optimized_url},
        asset_cache=cache,
        final_url="https://www.example.com/page",
        user_agent="pytest-agent",
        max_asset_mb=15,
        enabled=True,
    )

    record = cache.get(optimized_url)
    assert missing == []
    assert FakeClient.calls == [optimized_url, source_url]
    assert record is not None
    assert record.final_url == source_url
    assert record.content_type == "image/jpeg"
    assert record.data == b"jpg"


def test_fetch_missing_assets_repairs_cached_next_image_html_payload(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    optimized_url = (
        "https://www.example.com/_next/image?"
        "url=https%3A%2F%2Fcdn.example.com%2Fdiagram.png&w=1920&q=75"
    )
    source_url = "https://cdn.example.com/diagram.png"
    FakeClient = _fake_http_client(
        {
            optimized_url: _FakeResponse(
                url=optimized_url,
                status_code=200,
                content_type="text/html",
                content=b"<html>cached error</html>",
            ),
            source_url: _FakeResponse(
                url=source_url,
                status_code=200,
                content_type="image/png",
                content=b"png",
            ),
        }
    )

    monkeypatch.setattr("web2ru.assets.fetch_missing.httpx.Client", FakeClient)

    cache = AssetCache()
    ok = cache.put(
        url=optimized_url,
        final_url=optimized_url,
        content_type="text/html; charset=utf-8",
        data=b"<html>captured error</html>",
        source="capture",
        max_asset_mb=15,
    )
    assert ok is True

    missing = fetch_missing_assets(
        needed_urls={optimized_url},
        asset_cache=cache,
        final_url="https://www.example.com/page",
        user_agent="pytest-agent",
        max_asset_mb=15,
        enabled=True,
    )

    record = cache.get(optimized_url)
    assert missing == []
    assert FakeClient.calls == [optimized_url, source_url]
    assert record is not None
    assert record.final_url == source_url
    assert record.content_type == "image/png"
    assert record.data == b"png"
