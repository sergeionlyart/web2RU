from __future__ import annotations

import time
from urllib.parse import urlparse

from playwright.sync_api import Page, sync_playwright

from web2ru.assets.cache import AssetCache
from web2ru.config import RunConfig
from web2ru.models import OnlineRenderResult, ShadowDomStats


def run_online_render(config: RunConfig, asset_cache: AssetCache) -> tuple[OnlineRenderResult, str]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not config.headful)
        context = browser.new_context()
        page = context.new_page()

        def on_response(response: object) -> None:
            _capture_response_asset(response, asset_cache, config.max_asset_mb)

        page.on("response", on_response)

        page.goto(config.url, wait_until="domcontentloaded", timeout=config.timeout_ms)
        page.wait_for_timeout(config.post_load_wait_ms)
        height_before = _document_height(page)
        scroll_steps = 0
        if config.auto_scroll:
            scroll_steps = _auto_scroll(
                page,
                max_steps=config.max_scroll_steps,
                max_ms=config.max_scroll_ms,
            )
            page.wait_for_timeout(config.post_load_wait_ms)
        height_after = _document_height(page)

        shadow_stats = ShadowDomStats(enabled=config.shadow_dom_enabled)
        if config.shadow_dom_enabled:
            shadow_stats = _materialize_shadow_dom(page)

        html_dump = page.content()
        final_url = page.url
        user_agent = page.evaluate("() => navigator.userAgent")
        browser.close()

    result = OnlineRenderResult(
        final_url=final_url,
        html_dump=html_dump,
        shadow_dom=shadow_stats,
        scroll_steps=scroll_steps,
        height_before=height_before,
        height_after=height_after,
    )
    return result, user_agent


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
