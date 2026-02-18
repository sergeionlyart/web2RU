from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from web2ru.cli import app
from web2ru.models import OfflineResult, OnlineRenderResult, ShadowDomStats

runner = CliRunner()


def test_cli_smoke_without_network(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    def fake_online(config, asset_cache):  # type: ignore[no-untyped-def]
        return (
            OnlineRenderResult(
                final_url=config.url,
                html_dump="<html><body><main><p>Hello</p></main></body></html>",
                shadow_dom=ShadowDomStats(enabled=False),
                scroll_steps=0,
                height_before=100,
                height_after=100,
            ),
            "pytest-ua",
        )

    def fake_offline(config, online, asset_cache, user_agent):  # type: ignore[no-untyped-def]
        out = tmp_path / "out"
        out.mkdir(parents=True, exist_ok=True)
        index = out / "index.html"
        report = out / "report.json"
        index.write_text("<html></html>", encoding="utf-8")
        report.write_text("{}", encoding="utf-8")
        return OfflineResult(output_dir=out, index_path=index, report_path=report, report={})

    monkeypatch.setattr("web2ru.cli.run_online_render", fake_online)
    monkeypatch.setattr("web2ru.cli.run_offline_process", fake_offline)

    result = runner.invoke(app, ["https://example.com/page"])
    assert result.exit_code == 0
    assert "Output:" in result.stdout


def test_cli_fast_preset_applies_speed_defaults(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    captured = {}

    def fake_online(config, asset_cache):  # type: ignore[no-untyped-def]
        captured["config"] = config
        return (
            OnlineRenderResult(
                final_url=config.url,
                html_dump="<html><body><main><p>Hello</p></main></body></html>",
                shadow_dom=ShadowDomStats(enabled=False),
                scroll_steps=0,
                height_before=100,
                height_after=100,
            ),
            "pytest-ua",
        )

    def fake_offline(config, online, asset_cache, user_agent):  # type: ignore[no-untyped-def]
        out = tmp_path / "out-fast"
        out.mkdir(parents=True, exist_ok=True)
        index = out / "index.html"
        report = out / "report.json"
        index.write_text("<html></html>", encoding="utf-8")
        report.write_text("{}", encoding="utf-8")
        return OfflineResult(output_dir=out, index_path=index, report_path=report, report={})

    monkeypatch.setattr("web2ru.cli.run_online_render", fake_online)
    monkeypatch.setattr("web2ru.cli.run_offline_process", fake_offline)

    result = runner.invoke(app, ["https://example.com/page", "--fast"])
    assert result.exit_code == 0
    cfg = captured["config"]
    assert cfg.fast is True
    assert cfg.reasoning_effort == "none"
    assert cfg.max_retries == 3
    assert cfg.batch_chars == 8000
    assert cfg.max_items_per_batch == 100
    assert cfg.post_load_wait_ms == 700
    assert cfg.max_scroll_steps == 12
    assert cfg.max_scroll_ms == 10000


def test_cli_defaults_unchanged_without_fast(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    captured = {}

    def fake_online(config, asset_cache):  # type: ignore[no-untyped-def]
        captured["config"] = config
        return (
            OnlineRenderResult(
                final_url=config.url,
                html_dump="<html><body><main><p>Hello</p></main></body></html>",
                shadow_dom=ShadowDomStats(enabled=False),
                scroll_steps=0,
                height_before=100,
                height_after=100,
            ),
            "pytest-ua",
        )

    def fake_offline(config, online, asset_cache, user_agent):  # type: ignore[no-untyped-def]
        out = tmp_path / "out-defaults"
        out.mkdir(parents=True, exist_ok=True)
        index = out / "index.html"
        report = out / "report.json"
        index.write_text("<html></html>", encoding="utf-8")
        report.write_text("{}", encoding="utf-8")
        return OfflineResult(output_dir=out, index_path=index, report_path=report, report={})

    monkeypatch.setattr("web2ru.cli.run_online_render", fake_online)
    monkeypatch.setattr("web2ru.cli.run_offline_process", fake_offline)

    result = runner.invoke(app, ["https://example.com/page"])
    assert result.exit_code == 0
    cfg = captured["config"]
    assert cfg.fast is False
    assert cfg.reasoning_effort == "medium"
    assert cfg.max_retries == 6
    assert cfg.batch_chars == 4000
    assert cfg.max_items_per_batch == 40
    assert cfg.post_load_wait_ms == 1500
    assert cfg.max_scroll_steps == 25
    assert cfg.max_scroll_ms == 20000


def test_cli_fast_preset_respects_explicit_overrides(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    captured = {}

    def fake_online(config, asset_cache):  # type: ignore[no-untyped-def]
        captured["config"] = config
        return (
            OnlineRenderResult(
                final_url=config.url,
                html_dump="<html><body><main><p>Hello</p></main></body></html>",
                shadow_dom=ShadowDomStats(enabled=False),
                scroll_steps=0,
                height_before=100,
                height_after=100,
            ),
            "pytest-ua",
        )

    def fake_offline(config, online, asset_cache, user_agent):  # type: ignore[no-untyped-def]
        out = tmp_path / "out-fast-override"
        out.mkdir(parents=True, exist_ok=True)
        index = out / "index.html"
        report = out / "report.json"
        index.write_text("<html></html>", encoding="utf-8")
        report.write_text("{}", encoding="utf-8")
        return OfflineResult(output_dir=out, index_path=index, report_path=report, report={})

    monkeypatch.setattr("web2ru.cli.run_online_render", fake_online)
    monkeypatch.setattr("web2ru.cli.run_offline_process", fake_offline)

    result = runner.invoke(
        app,
        [
            "https://example.com/page",
            "--fast",
            "--max-retries",
            "9",
            "--reasoning-effort",
            "medium",
            "--batch-chars",
            "5000",
        ],
    )
    assert result.exit_code == 0
    cfg = captured["config"]
    assert cfg.fast is True
    assert cfg.max_retries == 9
    assert cfg.reasoning_effort == "medium"
    assert cfg.batch_chars == 5000
    # Still preset for parameters not explicitly overridden.
    assert cfg.max_items_per_batch == 100


def test_cli_surf_mode_invokes_surf_server(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    captured = {}

    class FakeSession:
        def __init__(self, *, config_template, same_origin_only, max_pages):  # type: ignore[no-untyped-def]
            captured["config"] = config_template
            captured["same_origin_only"] = same_origin_only
            captured["max_pages"] = max_pages
            self.session_root = tmp_path / "surf-session"
            self.session_root.mkdir(parents=True, exist_ok=True)

    def fake_serve_surf_session(*, session, port, open_in_browser):  # type: ignore[no-untyped-def]
        captured["served"] = True
        captured["port"] = port
        captured["open_in_browser"] = open_in_browser
        captured["session_root"] = session.session_root

    monkeypatch.setattr("web2ru.surf.session.SurfSession", FakeSession)
    monkeypatch.setattr("web2ru.surf.server.serve_surf_session", fake_serve_surf_session)

    result = runner.invoke(
        app,
        [
            "https://example.com/page",
            "--mode",
            "surf",
            "--surf-same-origin-only",
            "on",
            "--surf-max-pages",
            "15",
        ],
    )
    assert result.exit_code == 0
    assert captured["served"] is True
    assert captured["same_origin_only"] is True
    assert captured["max_pages"] == 15
    assert captured["config"].mode == "surf"
