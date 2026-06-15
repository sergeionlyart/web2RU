from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from urllib.parse import parse_qs, urljoin, urlparse

import httpx

from web2ru.assets.cache import AssetCache


@dataclass(slots=True)
class MissingAsset:
    url: str
    reason: str


@dataclass(slots=True)
class _FetchOutcome:
    url: str
    reason: str | None
    final_url: str | None = None
    content_type: str | None = None
    data: bytes | None = None


def fetch_missing_assets(
    *,
    needed_urls: set[str],
    asset_cache: AssetCache,
    final_url: str,
    user_agent: str,
    max_asset_mb: int,
    enabled: bool,
    timeout_seconds: float = 20.0,
    max_workers: int = 6,
) -> list[MissingAsset]:
    missing: list[MissingAsset] = []
    to_fetch: list[str] = []

    for url in sorted(needed_urls):
        cached_record = asset_cache.get(url)
        if cached_record is not None and not _is_invalid_next_image_payload(
            url,
            cached_record.content_type,
        ):
            continue
        if not enabled:
            missing.append(MissingAsset(url=url, reason="disabled"))
            continue
        to_fetch.append(url)

    if not to_fetch:
        return missing

    with httpx.Client(
        follow_redirects=True,
        timeout=timeout_seconds,
        headers={"User-Agent": user_agent, "Referer": final_url},
    ) as client:
        if len(to_fetch) <= 1:
            outcomes = [_fetch_one(client, to_fetch[0])]
        else:
            worker_count = max(1, min(max_workers, len(to_fetch)))
            outcomes = []
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = [executor.submit(_fetch_one, client, url) for url in to_fetch]
                for future in as_completed(futures):
                    outcomes.append(future.result())

    for outcome in sorted(outcomes, key=lambda item: item.url):
        if outcome.reason is not None:
            missing.append(MissingAsset(url=outcome.url, reason=outcome.reason))
            continue
        if outcome.data is None or outcome.final_url is None:
            missing.append(MissingAsset(url=outcome.url, reason="error:empty_response"))
            continue
        ok = asset_cache.put(
            url=outcome.url,
            final_url=outcome.final_url,
            content_type=outcome.content_type,
            data=outcome.data,
            source="fetch_missing",
            max_asset_mb=max_asset_mb,
        )
        if not ok:
            missing.append(MissingAsset(url=outcome.url, reason="size_limit"))

    return missing


def _fetch_one(client: httpx.Client, url: str) -> _FetchOutcome:
    try:
        response = client.get(url)
    except Exception as exc:  # noqa: BLE001 - keep pipeline resilient
        fallback = _fetch_next_image_source(client, url)
        if fallback is not None:
            return fallback
        return _FetchOutcome(url=url, reason=f"error:{type(exc).__name__}")

    if response.status_code >= 400:
        fallback = _fetch_next_image_source(client, url)
        if fallback is not None:
            return fallback
        return _FetchOutcome(url=url, reason=f"http_{response.status_code}")

    content_type = response.headers.get("content-type")
    if _is_invalid_next_image_payload(url, content_type):
        fallback = _fetch_next_image_source(client, url)
        if fallback is not None:
            return fallback
        return _FetchOutcome(url=url, reason="invalid_content_type")

    return _FetchOutcome(
        url=url,
        reason=None,
        final_url=str(response.url),
        content_type=content_type,
        data=response.content,
    )


def _fetch_next_image_source(
    client: httpx.Client,
    original_url: str,
) -> _FetchOutcome | None:
    source_url = _next_image_source_url(original_url)
    if source_url is None:
        return None

    try:
        response = client.get(source_url)
    except Exception:  # noqa: BLE001 - fallback failure must not stop the pipeline
        return None

    if response.status_code >= 400:
        return None

    content_type = response.headers.get("content-type")
    if not _is_image_content_type(content_type):
        return None

    return _FetchOutcome(
        url=original_url,
        reason=None,
        final_url=str(response.url),
        content_type=content_type,
        data=response.content,
    )


def _next_image_source_url(url: str) -> str | None:
    parsed = urlparse(url)
    if "/_next/image" not in parsed.path:
        return None

    source_values = parse_qs(parsed.query).get("url")
    if not source_values or not source_values[0]:
        return None

    source_url = urljoin(url, source_values[0])
    source_parsed = urlparse(source_url)
    if source_parsed.scheme not in {"http", "https"} or not source_parsed.netloc:
        return None
    if source_url == url:
        return None
    return source_url


def _is_invalid_next_image_payload(url: str, content_type: str | None) -> bool:
    if _next_image_source_url(url) is None or content_type is None:
        return False
    return not _is_image_content_type(content_type)


def _is_image_content_type(content_type: str | None) -> bool:
    if content_type is None:
        return False
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type.startswith("image/")
