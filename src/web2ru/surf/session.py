from __future__ import annotations

import threading
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import urljoin

from web2ru.assets.cache import AssetCache
from web2ru.config import RunConfig
from web2ru.pipeline.interstitial import looks_like_access_interstitial
from web2ru.pipeline.offline_process import run_offline_process
from web2ru.pipeline.online_render import run_online_render
from web2ru.surf.manifest import ManifestPage, SurfManifest
from web2ru.surf.router import (
    build_go_route,
    canonicalize_source_url,
    page_key_for_url,
    same_origin,
    split_fragment,
)


@dataclass(slots=True)
class SurfPageResult:
    source_url: str
    page_key: str
    output_dir: Path
    fragment: str = ""


class SurfSession:
    def __init__(
        self,
        *,
        config_template: RunConfig,
        same_origin_only: bool,
        max_pages: int,
    ) -> None:
        self._config_template = config_template
        self.same_origin_only = same_origin_only
        self.max_pages = max_pages
        self.origin_url = canonicalize_source_url(config_template.url)

        self.session_root = config_template.output_root / _session_slug(
            self.origin_url,
            same_origin_only=self.same_origin_only,
        )
        self.pages_root = self.session_root / "pages"
        self.pages_root.mkdir(parents=True, exist_ok=True)
        self.manifest = SurfManifest.load_or_create(
            path=self.session_root / "manifest.json",
            origin_url=self.origin_url,
        )

        self._lock = threading.Lock()
        self._inflight: dict[str, threading.Event] = {}

    def map_anchor_href(self, absolute_href: str) -> str | None:
        try:
            canonical = canonicalize_source_url(absolute_href)
        except ValueError:
            return None
        if self.same_origin_only and not same_origin(canonical, self.origin_url):
            return None
        return build_go_route(absolute_href)

    def ensure_page_for_navigation(self, requested_url: str) -> SurfPageResult:
        raw = requested_url.strip()
        if not raw:
            raise ValueError("URL is empty")
        absolute = raw
        if "://" not in raw:
            absolute = urljoin(self.origin_url, raw)
        canonical, fragment = split_fragment(absolute)
        canonical = canonicalize_source_url(canonical)
        if self.same_origin_only and not same_origin(canonical, self.origin_url):
            raise ValueError("Cross-origin navigation is disabled in surf mode")

        page = self._ensure_page(canonical)
        output_dir = self._resolve_output_dir(page)
        return SurfPageResult(
            source_url=canonical,
            page_key=page.page_key,
            output_dir=output_dir,
            fragment=fragment,
        )

    def get_page_output_dir(self, page_key: str) -> Path | None:
        with self._lock:
            page = self.manifest.get_by_page_key(page_key)
            if page is None or page.status != "ready" or page.output_dir is None:
                return None
            output_dir = self.session_root / page.output_dir
        index_path = output_dir / "index.html"
        if not index_path.exists():
            return None
        if _index_contains_interstitial(index_path):
            with self._lock:
                current = self.manifest.get_by_page_key(page_key)
                if current is not None and current.status == "ready":
                    self.manifest.mark_failed(
                        source_url=current.source_url,
                        page_key=current.page_key,
                        error="stale interstitial output detected; rebuilding required",
                    )
            return None
        return output_dir

    def get_source_url_by_page_key(self, page_key: str) -> str | None:
        with self._lock:
            page = self.manifest.get_by_page_key(page_key)
            if page is None:
                return None
            return page.source_url

    def _ensure_page(self, source_url: str) -> ManifestPage:
        canonical = canonicalize_source_url(source_url)
        while True:
            owned_event: threading.Event | None = None
            wait_event: threading.Event | None = None
            with self._lock:
                existing = self.manifest.get_by_url(canonical)
                if (
                    existing is not None
                    and existing.status == "ready"
                    and existing.output_dir is not None
                ):
                    output_dir = self.session_root / existing.output_dir
                    index_path = output_dir / "index.html"
                    if index_path.exists() and not _index_contains_interstitial(index_path):
                        return existing
                    self.manifest.mark_failed(
                        source_url=existing.source_url,
                        page_key=existing.page_key,
                        error="stale interstitial output detected; rebuilding required",
                    )

                inflight = self._inflight.get(canonical)
                if inflight is not None:
                    wait_event = inflight
                else:
                    if existing is None and self.manifest.ready_pages_count() >= self.max_pages:
                        raise RuntimeError(f"surf max pages reached: {self.max_pages}")
                    page_key = page_key_for_url(canonical)
                    self.manifest.mark_running(source_url=canonical, page_key=page_key)
                    owned_event = threading.Event()
                    self._inflight[canonical] = owned_event

            if wait_event is not None:
                wait_event.wait()
                continue
            if owned_event is None:
                continue
            try:
                return self._build_page(canonical)
            finally:
                with self._lock:
                    done = self._inflight.pop(canonical, None)
                    if done is not None:
                        done.set()

    def _build_page(self, source_url: str) -> ManifestPage:
        page_key = page_key_for_url(source_url)
        cfg = replace(
            self._config_template,
            url=source_url,
            open_result=False,
            serve=False,
            output_root=self.pages_root,
        )
        asset_cache = AssetCache()
        try:
            online, user_agent = run_online_render(cfg, asset_cache)
            offline = run_offline_process(
                config=cfg,
                online=online,
                asset_cache=asset_cache,
                user_agent=user_agent,
                map_anchor_href=self.map_anchor_href,
            )
        except Exception as exc:
            with self._lock:
                return self.manifest.mark_failed(
                    source_url=source_url,
                    page_key=page_key,
                    error=f"{type(exc).__name__}: {exc}",
                )

        relative_output = str(offline.output_dir.relative_to(self.session_root))
        with self._lock:
            return self.manifest.mark_ready(
                source_url=source_url,
                page_key=page_key,
                output_dir=relative_output,
            )

    def _resolve_output_dir(self, page: ManifestPage) -> Path:
        if page.status != "ready" or page.output_dir is None:
            message = page.error or "page is not ready"
            raise RuntimeError(message)
        output_dir = self.session_root / page.output_dir
        if not (output_dir / "index.html").exists():
            raise RuntimeError("ready page output is missing index.html")
        return output_dir


def _session_slug(origin_url: str, *, same_origin_only: bool) -> str:
    page_key = page_key_for_url(origin_url)
    host = origin_url.split("://", 1)[1].split("/", 1)[0]
    mode_suffix = "same" if same_origin_only else "any"
    return f"surf-{host}-{page_key[:8]}-{mode_suffix}"


def _index_contains_interstitial(index_path: Path) -> bool:
    try:
        html_text = index_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return looks_like_access_interstitial(html_text)
