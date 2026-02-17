from __future__ import annotations

from pathlib import Path

import pytest

from web2ru.config import RunConfig
from web2ru.models import OfflineResult, OnlineRenderResult, ShadowDomStats
from web2ru.surf.session import SurfSession


def test_surf_session_builds_and_reuses_ready_page(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    calls = {"online": 0, "offline": 0}

    def fake_online(config, asset_cache):  # type: ignore[no-untyped-def]
        calls["online"] += 1
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

    def fake_offline(config, online, asset_cache, user_agent, map_anchor_href=None):  # type: ignore[no-untyped-def]
        calls["offline"] += 1
        assert map_anchor_href is not None
        mapped = map_anchor_href("https://example.com/next")
        assert mapped is not None
        slug = f"page-{calls['offline']}"
        out = config.output_root / slug
        out.mkdir(parents=True, exist_ok=True)
        index = out / "index.html"
        report = out / "report.json"
        index.write_text("<html></html>", encoding="utf-8")
        report.write_text("{}", encoding="utf-8")
        return OfflineResult(output_dir=out, index_path=index, report_path=report, report={})

    monkeypatch.setattr("web2ru.surf.session.run_online_render", fake_online)
    monkeypatch.setattr("web2ru.surf.session.run_offline_process", fake_offline)

    cfg = RunConfig(
        url="https://example.com/start",
        output_root=tmp_path,
        mode="surf",
        freeze_js="on",
    )
    session = SurfSession(config_template=cfg, same_origin_only=True, max_pages=5)

    first = session.ensure_page_for_navigation("https://example.com/docs/a#intro")
    second = session.ensure_page_for_navigation("https://example.com/docs/a#intro")

    assert first.page_key == second.page_key
    assert first.fragment == "intro"
    assert second.fragment == "intro"
    assert calls["online"] == 1
    assert calls["offline"] == 1
    assert (first.output_dir / "index.html").exists()
    assert session.get_page_output_dir(first.page_key) == first.output_dir


def test_surf_session_rejects_cross_origin_when_disabled(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
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

    def fake_offline(config, online, asset_cache, user_agent, map_anchor_href=None):  # type: ignore[no-untyped-def]
        out = config.output_root / "page"
        out.mkdir(parents=True, exist_ok=True)
        index = out / "index.html"
        report = out / "report.json"
        index.write_text("<html></html>", encoding="utf-8")
        report.write_text("{}", encoding="utf-8")
        return OfflineResult(output_dir=out, index_path=index, report_path=report, report={})

    monkeypatch.setattr("web2ru.surf.session.run_online_render", fake_online)
    monkeypatch.setattr("web2ru.surf.session.run_offline_process", fake_offline)

    cfg = RunConfig(
        url="https://example.com/start",
        output_root=tmp_path,
        mode="surf",
        freeze_js="on",
    )
    session = SurfSession(config_template=cfg, same_origin_only=True, max_pages=2)
    session.ensure_page_for_navigation("https://example.com/start")

    with pytest.raises(ValueError):
        session.ensure_page_for_navigation("https://another.example.org/page")
