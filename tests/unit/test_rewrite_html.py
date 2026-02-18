from __future__ import annotations

from web2ru.assets.rewrite_html import rewrite_html_urls
from web2ru.assets.scan import parse_html


def test_rewrite_html_urls_preserves_non_url_meta_content() -> None:
    root = parse_html(
        """
        <html>
          <head>
            <meta name="viewport" content="width=device-width,initial-scale=1">
            <meta name="author" content="Simon Willison">
            <meta property="og:image" content="https://example.com/img/cover.jpg">
          </head>
          <body></body>
        </html>
        """
    )

    rewrite_html_urls(
        root,
        final_url="https://example.com/page",
        map_url=lambda url: f"./assets/{url.rsplit('/', 1)[-1]}",
    )

    viewport = root.xpath("//meta[@name='viewport']")[0]
    author = root.xpath("//meta[@name='author']")[0]
    og_image = root.xpath("//meta[@property='og:image']")[0]
    assert viewport.get("content") == "width=device-width,initial-scale=1"
    assert author.get("content") == "Simon Willison"
    assert og_image.get("content") == "./assets/cover.jpg"


def test_rewrite_html_urls_rewrites_anchor_links_with_mapper() -> None:
    root = parse_html(
        """
        <html>
          <body>
            <a id="same-origin" href="/docs/page-two">Page two</a>
            <a id="fragment-only" href="#section-1">Fragment</a>
            <a id="external" href="https://example.org/page">External</a>
          </body>
        </html>
        """
    )

    rewrite_html_urls(
        root,
        final_url="https://example.com/page-one",
        map_url=lambda url: f"./assets/{url.rsplit('/', 1)[-1]}",
        map_anchor_href=lambda href: (
            f"/__web2ru__/go?url={href}" if href.startswith("https://example.com/") else None
        ),
    )

    same_origin = root.xpath("//a[@id='same-origin']")[0]
    fragment_only = root.xpath("//a[@id='fragment-only']")[0]
    external = root.xpath("//a[@id='external']")[0]
    assert same_origin.get("href") == "/__web2ru__/go?url=https://example.com/docs/page-two"
    assert fragment_only.get("href") == "#section-1"
    assert external.get("href") == "https://example.org/page"
