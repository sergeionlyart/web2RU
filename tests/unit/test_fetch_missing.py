from __future__ import annotations

import threading

from web2ru.assets.cache import AssetCache
from web2ru.assets.fetch_missing import fetch_missing_assets


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
