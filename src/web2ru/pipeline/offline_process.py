from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from lxml import etree, html

from web2ru.apply.apply_attrs import apply_attributes
from web2ru.apply.apply_blocks import apply_blocks
from web2ru.assets.cache import AssetCache
from web2ru.assets.fetch_missing import fetch_missing_assets
from web2ru.assets.rewrite_html import rewrite_css_asset_records, rewrite_html_urls
from web2ru.assets.scan import parse_html, scan_needed_urls
from web2ru.config import RunConfig
from web2ru.extract.block_extractor import extract_attribute_items, extract_blocks
from web2ru.extract.scope import select_scope
from web2ru.freeze.freeze_js import freeze_html
from web2ru.models import OfflineResult, OnlineRenderResult
from web2ru.report.builder import build_base_report, write_report
from web2ru.translate.translator import Translator
from web2ru.utils import ensure_unique_slug, sha256_bytes, slugify_url


def run_offline_process(
    *,
    config: RunConfig,
    online: OnlineRenderResult,
    asset_cache: AssetCache,
    user_agent: str,
    map_anchor_href: Callable[[str], str | None] | None = None,
) -> OfflineResult:
    report = build_base_report(
        source_url=config.url,
        final_url=online.final_url,
        run_params=_run_params_for_report(config),
    )
    slug = ensure_unique_slug(config.output_root, slugify_url(online.final_url), online.final_url)
    output_dir = config.output_root / slug
    output_dir.mkdir(parents=True, exist_ok=True)

    root = parse_html(online.html_dump)
    _sanitize_base_url(root)
    _ensure_utf8_charset(root)

    css_by_url = _extract_css_from_cache(asset_cache)
    needed_urls = (
        scan_needed_urls(root, online.final_url, css_by_url) if config.asset_scan else set()
    )
    missing = fetch_missing_assets(
        needed_urls=needed_urls,
        asset_cache=asset_cache,
        final_url=online.final_url,
        user_agent=user_agent,
        max_asset_mb=config.max_asset_mb,
        enabled=config.fetch_missing_assets,
    )

    scope_root = select_scope(root, config.scope)
    blocks, excluded_ids = extract_blocks(
        scope_root,
        scope_mode=config.scope,
        translation_unit=config.translation_unit,
        exclude_selectors=config.exclude_selectors,
    )
    attrs = extract_attribute_items(
        scope_root,
        translate_attrs=config.translate_attrs,
        translate_alt=config.translate_alt,
        excluded_ids=excluded_ids,
    )

    translator_stats: dict[str, Any] = {}
    if config.api_key:
        translator = Translator(
            api_key=config.api_key,
            model=config.model,
            reasoning_effort=config.reasoning_effort,
            max_output_tokens=config.max_output_tokens,
            batch_chars=config.batch_chars,
            max_items_per_batch=config.max_items_per_batch,
            max_retries=config.max_retries,
            allow_empty_parts=config.allow_empty_parts,
            token_protect=config.token_protect,
            token_protect_strict=config.token_protect_strict,
            use_cache=config.use_translation_cache,
            cache_db_path=str(config.cache_dir / "translation_cache.sqlite3"),
        )
        try:
            translator.translate_blocks_and_attrs(blocks=blocks, attrs=attrs)
            translator_stats = asdict(translator.stats)
        finally:
            translator.close()
    else:
        report["warnings"].append("OPENAI_API_KEY is missing. Original text kept.")

    applied_parts = apply_blocks(root, blocks)
    applied_attrs = apply_attributes(root, attrs)

    def map_url(url: str) -> str:
        return asset_cache.ensure_local_mapping(url)

    rewrite_html_urls(
        root,
        final_url=online.final_url,
        map_url=map_url,
        map_anchor_href=map_anchor_href,
    )
    rewritten_css = rewrite_css_asset_records(css_text_by_url=css_by_url, map_url=map_url)
    _update_css_records(asset_cache, rewritten_css)

    freeze_counts = freeze_html(
        root,
        freeze_js_enabled=config.freeze_js_enabled,
        drop_noscript_mode=config.drop_noscript,
        block_iframe_enabled=config.block_iframe_enabled,
    )

    asset_cache.write_to_output(output_dir)
    html_text = html.tostring(root, encoding="unicode", method="html")
    index_path = output_dir / "index.html"
    index_path.write_text(html_text, encoding="utf-8")

    report["stats"] = {
        "blocks_total": len(blocks),
        "parts_total": sum(len(block.parts) for block in blocks),
        "attrs_total": len(attrs),
        "translated_parts": translator_stats.get("translated_parts", 0),
        "fallback_parts": translator_stats.get("fallback_parts", 0),
        "skipped_parts": max(
            sum(len(block.parts) for block in blocks) - translator_stats.get("translated_parts", 0),
            0,
        ),
        "token_protected_count": translator_stats.get("token_protected_count", 0),
    }
    batches_total = translator_stats.get("batches_total", 0)
    batch_chars_total = translator_stats.get("batch_chars_total", 0)
    report["llm"] = {
        "model": config.model,
        "reasoning_effort": config.reasoning_effort,
        "requests": translator_stats.get("requests", 0),
        "retries": translator_stats.get("retries", 0),
        "auto_split_depth": translator_stats.get("split_depth_max", 0),
        "cache_hits": translator_stats.get("cache_hits", 0),
        "batches_total": batches_total,
        "avg_batch_chars": (
            round(batch_chars_total / batches_total, 2) if batches_total > 0 else 0.0
        ),
        "glossary_terms": translator_stats.get("glossary_terms", 0),
    }
    total_items = report["stats"]["parts_total"] + report["stats"]["attrs_total"]
    items_with_context = translator_stats.get("items_with_context", 0)
    context_chars_total = translator_stats.get("context_chars_total", 0)
    report["quality"] = {
        "items_with_context": items_with_context,
        "context_coverage_ratio": (
            round(items_with_context / total_items, 4) if total_items > 0 else 0.0
        ),
        "avg_context_chars": (
            round(context_chars_total / items_with_context, 2) if items_with_context > 0 else 0.0
        ),
        "glossary_terms": translator_stats.get("glossary_terms", 0),
    }
    report["shadow_dom"] = {
        "enabled": online.shadow_dom.enabled,
        "open_roots_found": online.shadow_dom.open_roots_found,
        "templates_inserted": online.shadow_dom.templates_inserted,
        "adopted_stylesheets_extracted": online.shadow_dom.adopted_stylesheets_extracted,
        "errors_count": len(online.shadow_dom.errors),
    }
    report["assets"] = {
        "captured_total": sum(
            1 for r in asset_cache.records.values() if r.source == "network_capture"
        ),
        "scan_found_total": len(needed_urls),
        "fetched_missing_total": sum(
            1 for r in asset_cache.records.values() if r.source == "fetch_missing"
        ),
        "missing_assets": [{"url": m.url, "reason": m.reason} for m in missing],
    }
    report["sanitization"] = freeze_counts
    report["validation"] = {
        "external_requests_detected": None,
        "offline_ok_default_mode": config.freeze_js_enabled,
    }
    report["apply"] = {
        "applied_parts": applied_parts,
        "applied_attrs": applied_attrs,
    }
    if translator_stats.get("failures"):
        report["errors"].extend(translator_stats["failures"])

    report_path = output_dir / "report.json"
    write_report(report, report_path)

    return OfflineResult(
        output_dir=output_dir,
        index_path=index_path,
        report_path=report_path,
        report=report,
    )


def _sanitize_base_url(root: html.HtmlElement) -> None:
    for base in list(root.xpath("//base")):
        parent = base.getparent()
        if parent is not None:
            parent.remove(base)


def _ensure_utf8_charset(root: html.HtmlElement) -> None:
    heads = root.xpath("//head")
    if not heads:
        return
    head = heads[0]
    if not isinstance(head, etree._Element):
        return

    charset_meta: etree._Element | None = None
    for node in head.xpath("./meta[@charset]"):
        if isinstance(node, etree._Element):
            charset_meta = node
            break

    if charset_meta is None:
        charset_meta = etree.Element("meta")
        charset_meta.tail = "\n"
        head.insert(0, charset_meta)
    charset_meta.set("charset", "utf-8")

    if head.index(charset_meta) != 0:
        head.remove(charset_meta)
        head.insert(0, charset_meta)

    for node in head.xpath("./meta[@http-equiv]"):
        if not isinstance(node, etree._Element):
            continue
        equiv = (node.get("http-equiv") or "").strip().lower()
        if equiv == "content-type":
            node.set("content", "text/html; charset=utf-8")


def _extract_css_from_cache(asset_cache: AssetCache) -> dict[str, str]:
    out: dict[str, str] = {}
    for record in asset_cache.records.values():
        content_type = (record.content_type or "").lower()
        if "text/css" in content_type or record.final_url.lower().endswith(".css"):
            try:
                out[record.final_url] = record.data.decode("utf-8", errors="replace")
            except Exception:
                continue
    return out


def _update_css_records(asset_cache: AssetCache, rewritten_css: dict[str, str]) -> None:
    for source_url, css_text in rewritten_css.items():
        record = asset_cache.get(source_url)
        if record is None:
            continue
        encoded = css_text.encode("utf-8")
        record.data = encoded
        record.size = len(encoded)
        record.sha256 = sha256_bytes(encoded)


def _run_params_for_report(config: RunConfig) -> dict[str, Any]:
    return {
        "fast": config.fast,
        "mode": config.mode,
        "surf_same_origin_only": config.surf_same_origin_only,
        "surf_max_pages": config.surf_max_pages,
        "model": config.model,
        "reasoning_effort": config.reasoning_effort,
        "timeout_ms": config.timeout_ms,
        "post_load_wait_ms": config.post_load_wait_ms,
        "auto_scroll": config.auto_scroll,
        "max_scroll_steps": config.max_scroll_steps,
        "max_scroll_ms": config.max_scroll_ms,
        "shadow_dom": config.shadow_dom,
        "scope": config.scope,
        "translation_unit": config.translation_unit,
        "allow_empty_parts": config.allow_empty_parts,
        "translate_attrs": config.translate_attrs,
        "translate_alt": config.translate_alt,
        "token_protect": config.token_protect,
        "token_protect_strict": config.token_protect_strict,
        "batch_chars": config.batch_chars,
        "max_items_per_batch": config.max_items_per_batch,
        "max_retries": config.max_retries,
        "max_asset_mb": config.max_asset_mb,
        "openai_min_interval_ms": config.openai_min_interval_ms,
        "asset_scan": config.asset_scan,
        "fetch_missing_assets": config.fetch_missing_assets,
        "freeze_js": config.freeze_js,
        "drop_noscript": config.drop_noscript,
        "block_iframe": config.block_iframe,
    }
