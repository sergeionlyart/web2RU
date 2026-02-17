from __future__ import annotations

from web2ru.assets.rewrite_css import rewrite_css_urls


def test_rewrite_css_urls_and_imports() -> None:
    css = """
    @import "theme/base.css";
    body { background: url("../img/bg.png"); }
    """
    out = rewrite_css_urls(
        css,
        css_base_url="https://example.com/static/css/main.css",
        map_url=lambda u: f"./assets/mapped/{u.split('/')[-1]}",
    )
    assert "./assets/mapped/base.css" in out
    assert "./assets/mapped/bg.png" in out
