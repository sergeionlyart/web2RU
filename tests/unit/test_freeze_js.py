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


def test_linkedin_overlay_is_neutralized_even_when_js_not_frozen() -> None:
    root = html.fromstring(
        """
        <html><head>
          <meta property="og:site_name" content="LinkedIn" />
        </head><body class="modal-open overflow-hidden" style="overflow:hidden;">
          <div class="top-level-modal-container">
            <div id="base-contextual-sign-in-modal" class="contextual-sign-in-modal">
              <div class="modal__overlay modal__overlay--visible"></div>
              <button class="modal__dismiss">Dismiss</button>
            </div>
          </div>
          <main>Article content</main>
        </body></html>
        """
    )
    counters = freeze_html(
        root,
        freeze_js_enabled=False,
        drop_noscript_mode="auto",
        block_iframe_enabled=False,
    )
    overlay = root.xpath("//*[@id='base-contextual-sign-in-modal']")[0]
    body = root.xpath("//body")[0]
    assert "display:none" in (overlay.get("style") or "")
    assert overlay.get("aria-hidden") == "true"
    assert "modal-open" not in (body.get("class") or "")
    assert "overflow:auto" in (body.get("style") or "")
    assert counters["overlays_neutralized_count"] >= 1
    assert counters["scroll_unlocks_count"] >= 1
