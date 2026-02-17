from __future__ import annotations

from dataclasses import dataclass

import httpx

from web2ru.assets.cache import AssetCache


@dataclass(slots=True)
class MissingAsset:
    url: str
    reason: str


def fetch_missing_assets(
    *,
    needed_urls: set[str],
    asset_cache: AssetCache,
    final_url: str,
    user_agent: str,
    max_asset_mb: int,
    enabled: bool,
    timeout_seconds: float = 20.0,
) -> list[MissingAsset]:
    missing: list[MissingAsset] = []
    for url in sorted(needed_urls):
        if asset_cache.has(url):
            continue
        if not enabled:
            missing.append(MissingAsset(url=url, reason="disabled"))
            continue
        try:
            with httpx.Client(
                follow_redirects=True,
                timeout=timeout_seconds,
                headers={"User-Agent": user_agent, "Referer": final_url},
            ) as client:
                response = client.get(url)
            if response.status_code >= 400:
                missing.append(MissingAsset(url=url, reason=f"http_{response.status_code}"))
                continue
            content_type = response.headers.get("content-type")
            ok = asset_cache.put(
                url=url,
                final_url=str(response.url),
                content_type=content_type,
                data=response.content,
                source="fetch_missing",
                max_asset_mb=max_asset_mb,
            )
            if not ok:
                missing.append(MissingAsset(url=url, reason="size_limit"))
        except Exception as exc:  # noqa: BLE001 - keep pipeline resilient
            missing.append(MissingAsset(url=url, reason=f"error:{type(exc).__name__}"))
    return missing
