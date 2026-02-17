from __future__ import annotations

from pathlib import Path

from web2ru.assets.cache import AssetCache
from web2ru.config import RunConfig
from web2ru.models import OnlineRenderResult, ShadowDomStats
from web2ru.pipeline.offline_process import run_offline_process


def test_offline_pipeline_writes_snapshot(tmp_path: Path) -> None:
    html_dump = """
    <html><head>
      <link rel="stylesheet" href="https://example.com/assets/app.css">
    </head>
    <body><main><p>Hello world</p></main></body></html>
    """
    cfg = RunConfig(
        url="https://example.com/page",
        output_root=tmp_path,
        asset_scan=True,
        fetch_missing_assets=False,
        freeze_js="on",
        api_key=None,
    )
    cache = AssetCache()
    cache.put(
        url="https://example.com/assets/app.css",
        final_url="https://example.com/assets/app.css",
        content_type="text/css",
        data=b"body { background:url('../img/a.png'); }",
        source="network_capture",
        max_asset_mb=15,
    )
    online = OnlineRenderResult(
        final_url="https://example.com/page",
        html_dump=html_dump,
        shadow_dom=ShadowDomStats(enabled=False),
        scroll_steps=0,
        height_before=1000,
        height_after=1000,
    )

    result = run_offline_process(
        config=cfg,
        online=online,
        asset_cache=cache,
        user_agent="pytest-agent",
    )
    assert result.index_path.exists()
    assert result.report_path.exists()
    html_text = result.index_path.read_text(encoding="utf-8")
    assert "./assets/" in html_text
    assert "https://example.com/assets/app.css" not in html_text
    assert "quality" in result.report
    assert "context_coverage_ratio" in result.report["quality"]
