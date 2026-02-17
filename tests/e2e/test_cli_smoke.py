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
