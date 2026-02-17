from __future__ import annotations

import os
import socketserver
import webbrowser
from contextlib import suppress
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import typer
from click.core import ParameterSource

from web2ru.assets.cache import AssetCache
from web2ru.config import RunConfig
from web2ru.env import load_env_chain
from web2ru.pipeline.offline_process import run_offline_process
from web2ru.pipeline.online_render import run_online_render

app = typer.Typer(add_completion=False, help="Web2RU offline translation snapshot utility.")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _env_or(default: str, *keys: str) -> str:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    return default


def _bool_from_on_off(value: str) -> bool:
    return value.lower() == "on"


def _is_default_param_source(ctx: typer.Context, name: str) -> bool:
    source = ctx.get_parameter_source(name)
    return source in {ParameterSource.DEFAULT, ParameterSource.DEFAULT_MAP}


@app.command()
def run(
    ctx: typer.Context,
    url: str = typer.Argument(..., help="Source page URL"),
    mode: str = typer.Option("single", "--mode", help="Run mode: single or surf"),
    fast: bool = typer.Option(False, "--fast", help="Use speed-oriented preset values"),
    open_result: bool = typer.Option(False, "--open", help="Open result in browser"),
    headful: bool = typer.Option(False, "--headful", help="Run Playwright in visible mode"),
    timeout_ms: int = typer.Option(60000, "--timeout-ms"),
    post_load_wait_ms: int = typer.Option(1500, "--post-load-wait-ms"),
    auto_scroll: str = typer.Option("on", "--auto-scroll"),
    shadow_dom: str = typer.Option(None, "--shadow-dom"),
    max_scroll_steps: int = typer.Option(25, "--max-scroll-steps"),
    max_scroll_ms: int = typer.Option(20000, "--max-scroll-ms"),
    scope: str = typer.Option("auto", "--scope"),
    exclude_selector: list[str] = typer.Option(None, "--exclude-selector"),
    translation_unit: str = typer.Option("block", "--translation-unit"),
    allow_empty_parts: str = typer.Option(None, "--allow-empty-parts"),
    translate_attrs: str = typer.Option("on", "--translate-attrs"),
    translate_alt: str = typer.Option("auto", "--translate-alt"),
    token_protect: str = typer.Option("on", "--token-protect"),
    token_protect_strict: str = typer.Option("off", "--token-protect-strict"),
    model: str = typer.Option(None, "--model"),
    reasoning_effort: str = typer.Option(None, "--reasoning-effort"),
    max_output_tokens: int = typer.Option(8192, "--max-output-tokens"),
    batch_chars: int = typer.Option(4000, "--batch-chars"),
    max_items_per_batch: int = typer.Option(40, "--max-items-per-batch"),
    max_retries: int = typer.Option(6, "--max-retries"),
    cache_dir: str = typer.Option(None, "--cache-dir"),
    no_asset_cache: bool = typer.Option(False, "--no-asset-cache"),
    no_translation_cache: bool = typer.Option(False, "--no-translation-cache"),
    max_asset_mb: int = typer.Option(15, "--max-asset-mb"),
    asset_scan: str = typer.Option("on", "--asset-scan"),
    fetch_missing_assets: str = typer.Option("on", "--fetch-missing-assets"),
    freeze_js: str = typer.Option("auto", "--freeze-js"),
    drop_noscript: str = typer.Option("auto", "--drop-noscript"),
    block_iframe: str = typer.Option("auto", "--block-iframe"),
    serve: str = typer.Option(None, "--serve"),
    serve_port: int = typer.Option(0, "--serve-port"),
    surf_same_origin_only: str = typer.Option(
        "on",
        "--surf-same-origin-only",
        help="In surf mode, allow only same-origin navigation",
    ),
    surf_max_pages: int = typer.Option(30, "--surf-max-pages"),
    log_level: str = typer.Option("info", "--log-level"),
) -> None:
    repo_root = _repo_root()
    load_env_chain(repo_root)
    mode_resolved = mode.strip().lower()
    if mode_resolved not in {"single", "surf"}:
        raise typer.BadParameter("`--mode` must be either `single` or `surf`.")
    if fast:
        if _is_default_param_source(ctx, "reasoning_effort"):
            reasoning_effort = "none"
        if _is_default_param_source(ctx, "max_retries"):
            max_retries = 3
        if _is_default_param_source(ctx, "batch_chars"):
            batch_chars = 8000
        if _is_default_param_source(ctx, "max_items_per_batch"):
            max_items_per_batch = 100
        if _is_default_param_source(ctx, "post_load_wait_ms"):
            post_load_wait_ms = 700
        if _is_default_param_source(ctx, "max_scroll_steps"):
            max_scroll_steps = 12
        if _is_default_param_source(ctx, "max_scroll_ms"):
            max_scroll_ms = 10000

    serve_resolved = _resolve_serve_flag(open_result=open_result, serve=serve)
    if mode_resolved == "surf":
        serve_resolved = True
    cfg = RunConfig(
        url=url,
        mode=mode_resolved,
        fast=fast,
        surf_same_origin_only=_bool_from_on_off(surf_same_origin_only),
        surf_max_pages=surf_max_pages,
        model=model or _env_or("gpt-5.1", "WEB2RU_MODEL"),
        reasoning_effort=reasoning_effort or _env_or("medium", "WEB2RU_REASONING_EFFORT"),
        max_output_tokens=max_output_tokens,
        batch_chars=batch_chars,
        max_items_per_batch=max_items_per_batch,
        max_retries=max_retries,
        timeout_ms=timeout_ms,
        post_load_wait_ms=post_load_wait_ms,
        auto_scroll=_bool_from_on_off(auto_scroll),
        max_scroll_steps=max_scroll_steps,
        max_scroll_ms=max_scroll_ms,
        shadow_dom=shadow_dom or _env_or("auto", "WEB2RU_SHADOW_DOM"),
        scope=scope,
        translation_unit=translation_unit,
        allow_empty_parts=_bool_from_on_off(
            allow_empty_parts or _env_or("on", "WEB2RU_ALLOW_EMPTY_PARTS")
        ),
        translate_attrs=_bool_from_on_off(translate_attrs),
        translate_alt=translate_alt,
        token_protect=_bool_from_on_off(token_protect),
        token_protect_strict=_bool_from_on_off(token_protect_strict),
        cache_dir=Path(cache_dir or _env_or(str(RunConfig(url=url).cache_dir), "WEB2RU_CACHE_DIR")),
        use_asset_cache=not no_asset_cache,
        use_translation_cache=not no_translation_cache,
        max_asset_mb=max_asset_mb,
        asset_scan=_bool_from_on_off(asset_scan),
        fetch_missing_assets=_bool_from_on_off(fetch_missing_assets),
        freeze_js=freeze_js,
        drop_noscript=drop_noscript,
        block_iframe=block_iframe,
        open_result=open_result,
        serve=serve_resolved,
        serve_port=serve_port,
        headful=headful,
        log_level=log_level,
        exclude_selectors=exclude_selector or [],
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    if cfg.mode == "surf":
        _run_surf_mode(cfg)
        return

    typer.echo("Web2RU: online render phase...")
    asset_cache = AssetCache()
    online, user_agent = run_online_render(cfg, asset_cache)

    typer.echo("Web2RU: offline processing phase...")
    offline = run_offline_process(
        config=cfg,
        online=online,
        asset_cache=asset_cache,
        user_agent=user_agent,
    )
    typer.echo(f"Output: {offline.output_dir}")
    typer.echo(f"Report: {offline.report_path}")

    if cfg.open_result:
        if cfg.serve:
            _serve_and_open(offline.output_dir, cfg.serve_port)
        else:
            webbrowser.open(offline.index_path.resolve().as_uri())


def _run_surf_mode(cfg: RunConfig) -> None:
    from web2ru.surf.server import serve_surf_session
    from web2ru.surf.session import SurfSession

    typer.echo("Web2RU: surf mode initial page build...")
    session = SurfSession(
        config_template=cfg,
        same_origin_only=cfg.surf_same_origin_only,
        max_pages=cfg.surf_max_pages,
    )
    initial = session.ensure_page_for_navigation(cfg.url)
    typer.echo(f"Surf session: {session.session_root}")
    typer.echo(f"Initial page: {initial.source_url}")
    serve_surf_session(session=session, port=cfg.serve_port, open_in_browser=cfg.open_result)


def _resolve_serve_flag(*, open_result: bool, serve: str | None) -> bool:
    if serve is None:
        return open_result
    return _bool_from_on_off(serve)


def _serve_and_open(output_dir: Path, port: int) -> None:
    handler = partial(SimpleHTTPRequestHandler, directory=str(output_dir))
    with ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        selected_port = _extract_server_port(httpd)
        url = f"http://127.0.0.1:{selected_port}/index.html"
        typer.echo(f"Serving at {url}")
        webbrowser.open(url)
        typer.echo("Press Ctrl+C to stop server.")
        with suppress(KeyboardInterrupt):
            httpd.serve_forever()


def _extract_server_port(httpd: socketserver.BaseServer) -> int:
    server_address = getattr(httpd, "server_address", ("127.0.0.1", 0))
    if isinstance(server_address, tuple) and len(server_address) >= 2:
        return int(server_address[1])
    return 0


def main() -> None:
    app()


if __name__ == "__main__":
    main()
