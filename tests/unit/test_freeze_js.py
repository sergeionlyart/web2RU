from __future__ import annotations

from lxml import html

from web2ru.freeze.freeze_js import freeze_html


def test_freeze_disables_scripts_and_handlers() -> None:
    root = html.fromstring(
        """
        <html><head>
          <meta http-equiv="refresh" content="0;url=https://example.com">
        </head><body>
          <script src="https://cdn.example/app.js"></script>
          <a href="javascript:alert(1)" onclick="x()">Click</a>
          <iframe src="https://example.com/embed"></iframe>
        </body></html>
        """
    )
    counters = freeze_html(
        root,
        freeze_js_enabled=True,
        drop_noscript_mode="auto",
        block_iframe_enabled=True,
    )
    script = root.xpath("//script")[0]
    assert script.get("src") is None
    assert script.get("type") == "application/x-web2ru-disabled"
    anchor = root.xpath("//a")[0]
    assert anchor.get("href") == "#"
    assert "onclick" not in anchor.attrib
    iframe = root.xpath("//iframe")[0]
    assert iframe.get("src") == "about:blank"
    assert counters["scripts_disabled_count"] >= 1
