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


def test_funding_choices_consent_overlay_is_neutralized() -> None:
    root = html.fromstring(
        """
        <html style="overflow:hidden;"><body style="overflow:hidden;" class="no-scroll">
          <main>Article content</main>
          <div class="fc-consent-root">
            <div class="fc-dialog-overlay"></div>
            <div class="fc-dialog-container" role="dialog" aria-modal="true">
              <button class="fc-confirm-choices">Confirm choices</button>
            </div>
          </div>
        </body></html>
        """
    )
    counters = freeze_html(
        root,
        freeze_js_enabled=True,
        drop_noscript_mode="auto",
        block_iframe_enabled=True,
    )
    body = root.xpath("//body")[0]
    assert not root.xpath("//*[contains(@class, 'fc-consent-root')]")
    assert not root.xpath("//*[contains(@class, 'fc-dialog-container')]")
    assert "no-scroll" not in (body.get("class") or "")
    assert "overflow:auto" in (body.get("style") or "")
    assert counters["overlays_neutralized_count"] >= 1
    assert counters["scroll_unlocks_count"] >= 1


def test_sourcepoint_consent_overlay_unlocks_document_scroll() -> None:
    root = html.fromstring(
        """
        <html class="sp-message-open"><head>
          <style>
            .sp-message-open { height: 100vh !important; width: 100vw !important; }
            .sp-message-open body { overflow: hidden !important; position: fixed !important; }
          </style>
        </head><body>
          <main style="min-height: 3000px;">Article content</main>
          <div id="sp_message_container_1160204" role="dialog" style="display: block;">
            <iframe id="sp_message_iframe_1160204" title="SP Consent Message"></iframe>
          </div>
        </body></html>
        """
    )
    counters = freeze_html(
        root,
        freeze_js_enabled=True,
        drop_noscript_mode="auto",
        block_iframe_enabled=True,
    )
    html_node = root.xpath("//html")[0]
    body = root.xpath("//body")[0]
    assert not root.xpath("//*[starts-with(@id, 'sp_message_container_')]")
    assert not root.xpath("//*[starts-with(@id, 'sp_message_iframe_')]")
    assert "sp-message-open" not in (html_node.get("class") or "")
    assert "overflow:auto" in (body.get("style") or "")
    assert "position:static" in (body.get("style") or "")
    assert "height:auto" in (html_node.get("style") or "")
    assert counters["overlays_neutralized_count"] >= 1
    assert counters["scroll_unlocks_count"] >= 1
