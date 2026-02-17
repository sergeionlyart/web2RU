from __future__ import annotations

import asyncio
import time
from typing import Any, cast
from urllib.parse import urlparse

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from web2ru.assets.cache import AssetCache
from web2ru.config import RunConfig
from web2ru.models import OnlineRenderResult, ShadowDomStats
from web2ru.pipeline.interstitial import looks_like_access_interstitial
from web2ru.pipeline.session_policy import (
    SessionPolicy,
    build_session_policy,
    enforce_domain_rate_limit,
    load_storage_state,
    persist_storage_state,
    resolve_storage_state_input,
)

_INTERSTITIAL_ERROR = (
    "Access interstitial detected during online render; target content is blocked by anti-bot challenge."
)


def run_online_render(config: RunConfig, asset_cache: AssetCache) -> tuple[OnlineRenderResult, str]:
    policy = build_session_policy(
        url=config.url,
        cache_dir=config.cache_dir,
        openai_min_interval_ms=config.openai_min_interval_ms,
    )

    with sync_playwright() as p:
        if policy.use_persistent_profile:
            return _run_with_persistent_context(
                playwright=p,
                config=config,
                asset_cache=asset_cache,
                policy=policy,
            )

        browser = p.chromium.launch(
            headless=not config.headful,
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            return _run_with_ephemeral_contexts(
                browser=browser,
                config=config,
                asset_cache=asset_cache,
                policy=policy,
            )
        finally:
            browser.close()


def _run_with_ephemeral_contexts(
    *,
    browser: Browser,
    config: RunConfig,
    asset_cache: AssetCache,
    policy: SessionPolicy,
) -> tuple[OnlineRenderResult, str]:
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        context = _new_ephemeral_context(browser=browser, policy=policy)
        try:
            _restore_context_storage_state(context=context, policy=policy)
            enforce_domain_rate_limit(policy=policy, cache_dir=config.cache_dir)
            return _render_with_context(context=context, config=config, asset_cache=asset_cache)
        except RuntimeError as exc:
            if str(exc) != _INTERSTITIAL_ERROR:
                raise
            if attempt < max_attempts:
                time.sleep(1.0 * attempt)
        finally:
            _persist_context_storage_state(context=context, policy=policy)
            context.close()
    raise RuntimeError(f"{_INTERSTITIAL_ERROR} (attempts={max_attempts})")


def _run_with_persistent_context(
    *,
    playwright: Playwright,
    config: RunConfig,
    asset_cache: AssetCache,
    policy: SessionPolicy,
) -> tuple[OnlineRenderResult, str]:
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        context = _new_persistent_context(playwright=playwright, config=config, policy=policy)
        try:
            _restore_context_storage_state(context=context, policy=policy)
            enforce_domain_rate_limit(policy=policy, cache_dir=config.cache_dir)
            return _render_with_context(context=context, config=config, asset_cache=asset_cache)
        except RuntimeError as exc:
            if str(exc) != _INTERSTITIAL_ERROR:
                raise
            if attempt < max_attempts:
                time.sleep(1.0 * attempt)
        finally:
            _persist_context_storage_state(context=context, policy=policy)
            context.close()
    raise RuntimeError(f"{_INTERSTITIAL_ERROR} (attempts={max_attempts})")


def _new_ephemeral_context(*, browser: Browser, policy: SessionPolicy) -> BrowserContext:
    storage_state_input = resolve_storage_state_input(policy)
    if storage_state_input is not None:
        return browser.new_context(storage_state=storage_state_input)
    return browser.new_context()


def _new_persistent_context(
    *, playwright: Playwright, config: RunConfig, policy: SessionPolicy
) -> BrowserContext:
    if policy.profile_dir is None:
        raise RuntimeError("persistent profile is not configured")

    policy.profile_dir.mkdir(parents=True, exist_ok=True)
    return playwright.chromium.launch_persistent_context(
        str(policy.profile_dir),
        headless=not config.headful,
        args=["--disable-blink-features=AutomationControlled"],
    )


def _restore_context_storage_state(*, context: BrowserContext, policy: SessionPolicy) -> None:
    payload = load_storage_state(policy)
    if payload is None:
        return
    cookies = payload.get("cookies")
    if not isinstance(cookies, list) or not cookies:
        return
    try:
        context.add_cookies(cast(Any, cookies))
    except Exception:
        return


def _persist_context_storage_state(*, context: BrowserContext, policy: SessionPolicy) -> None:
    if policy.storage_state_path is None:
        return
    try:
        persist_storage_state(policy, context.storage_state())
    except Exception:
        return


def _render_with_context(
    *, context: BrowserContext, config: RunConfig, asset_cache: AssetCache
) -> tuple[OnlineRenderResult, str]:
    page = context.new_page()
    page.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', {
          get: () => undefined
        });
        """
    )

    def on_response(response: object) -> None:
        _capture_response_asset(response, asset_cache, config.max_asset_mb)

    page.on("response", on_response)

    page.goto(config.url, wait_until="domcontentloaded", timeout=config.timeout_ms)
    page.wait_for_timeout(config.post_load_wait_ms)
    _ensure_not_interstitial(
        page,
        timeout_ms=config.timeout_ms,
        post_load_wait_ms=config.post_load_wait_ms,
        headful=config.headful,
    )
    height_before = _document_height(page)
    scroll_steps = 0
    if config.auto_scroll:
        scroll_steps = _auto_scroll(
            page,
            max_steps=config.max_scroll_steps,
            max_ms=config.max_scroll_ms,
        )
        page.wait_for_timeout(config.post_load_wait_ms)
    _ensure_not_interstitial(
        page,
        timeout_ms=config.timeout_ms,
        post_load_wait_ms=config.post_load_wait_ms,
        headful=config.headful,
    )
    height_after = _document_height(page)

    shadow_stats = ShadowDomStats(enabled=config.shadow_dom_enabled)
    if config.shadow_dom_enabled:
        shadow_stats = _materialize_shadow_dom(page)

    html_dump = page.content()
    final_url = page.url
    user_agent = page.evaluate("() => navigator.userAgent")
    result = OnlineRenderResult(
        final_url=final_url,
        html_dump=html_dump,
        shadow_dom=shadow_stats,
        scroll_steps=scroll_steps,
        height_before=height_before,
        height_after=height_after,
    )
    return result, user_agent


def _ensure_not_interstitial(
    page: Page, *, timeout_ms: int, post_load_wait_ms: int, headful: bool
) -> None:
    poll_ms = 500
    max_wait_ms = max(30000, min(timeout_ms, 180000))
    start = time.monotonic()
    deadline = start + (max_wait_ms / 1000)
    retry_reload = not headful
    reload_after = start + (max_wait_ms / 2000)
    while True:
        html_text = page.content()
        if not looks_like_access_interstitial(html_text):
            return
        now = time.monotonic()
        if retry_reload and now >= reload_after:
            retry_reload = False
            try:
                page.reload(wait_until="domcontentloaded", timeout=timeout_ms)
                page.wait_for_timeout(post_load_wait_ms)
                continue
            except Exception:
                pass
        if time.monotonic() >= deadline:
            break
        page.wait_for_timeout(poll_ms)

    raise RuntimeError(_INTERSTITIAL_ERROR)


def _capture_response_asset(response: object, asset_cache: AssetCache, max_asset_mb: int) -> None:
    # Playwright response object in runtime; typed as object here to avoid strict dependency on Protocols.
    try:
        url = response.url  # type: ignore[attr-defined]
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return
        headers = response.headers  # type: ignore[attr-defined]
        content_type = headers.get("content-type") if isinstance(headers, dict) else None
        data = response.body()  # type: ignore[attr-defined]
        final_url = response.url  # type: ignore[attr-defined]
        asset_cache.put(
            url=url,
            final_url=final_url,
            content_type=content_type,
            data=data,
            source="network_capture",
            max_asset_mb=max_asset_mb,
        )
    except asyncio.CancelledError:
        return
    except Exception:
        # Best effort capture only.
        return


def _document_height(page: Page) -> int:
    return int(
        page.evaluate(
            "() => Math.max(document.body?.scrollHeight || 0, document.documentElement?.scrollHeight || 0)"
        )
    )


def _auto_scroll(page: Page, *, max_steps: int, max_ms: int) -> int:
    start = time.monotonic()
    steps = 0
    prev_height = _document_height(page)
    while steps < max_steps:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        if elapsed_ms >= max_ms:
            break
        page.evaluate("() => window.scrollBy(0, Math.floor(window.innerHeight * 0.9))")
        page.wait_for_timeout(250)
        steps += 1
        height = _document_height(page)
        if height <= prev_height and steps > 3:
            # Page stopped growing; enough for lazy-loading pass.
            break
        prev_height = height
    return steps


def _materialize_shadow_dom(page: Page) -> ShadowDomStats:
    script = """
    () => {
      const stats = {
        enabled: true,
        open_roots_found: 0,
        templates_inserted: 0,
        adopted_stylesheets_extracted: 0,
        errors: [],
      };
      const walk = (root) => {
        const nodes = root.querySelectorAll ? root.querySelectorAll('*') : [];
        for (const host of nodes) {
          try {
            const sr = host.shadowRoot;
            if (!sr || sr.mode !== 'open') continue;
            stats.open_roots_found += 1;
            let existing = null;
            for (const child of host.children) {
              if (child.tagName === 'TEMPLATE' && child.hasAttribute('shadowrootmode')) {
                existing = child;
                break;
              }
            }
            if (!existing) {
              const tpl = document.createElement('template');
              tpl.setAttribute('shadowrootmode', 'open');
              tpl.setAttribute('data-web2ru-shadow', '1');
              const frag = document.createElement('div');
              frag.innerHTML = sr.innerHTML;
              if (sr.adoptedStyleSheets && sr.adoptedStyleSheets.length > 0) {
                let css = '';
                for (const sh of sr.adoptedStyleSheets) {
                  try {
                    if (sh.cssRules) {
                      for (const rule of sh.cssRules) css += rule.cssText + '\\n';
                    }
                  } catch (e) {}
                }
                if (css) {
                  const st = document.createElement('style');
                  st.setAttribute('data-web2ru-adopted', '1');
                  st.textContent = css;
                  tpl.content.appendChild(st);
                  stats.adopted_stylesheets_extracted += 1;
                }
              }
              while (frag.firstChild) tpl.content.appendChild(frag.firstChild);
              host.insertBefore(tpl, host.firstChild);
              stats.templates_inserted += 1;
            }
            walk(sr);
          } catch (e) {
            stats.errors.push(String(e));
          }
        }
      };
      walk(document);
      return stats;
    }
    """
    result = page.evaluate(script)
    return ShadowDomStats(
        enabled=bool(result.get("enabled", True)),
        open_roots_found=int(result.get("open_roots_found", 0)),
        templates_inserted=int(result.get("templates_inserted", 0)),
        adopted_stylesheets_extracted=int(result.get("adopted_stylesheets_extracted", 0)),
        errors=[str(x) for x in result.get("errors", [])],
    )
