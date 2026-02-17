from __future__ import annotations

from web2ru.pipeline.interstitial import looks_like_access_interstitial


def test_detects_cloudflare_just_a_moment_page() -> None:
    html_text = """
    <html>
      <head><title>Just a moment...</title></head>
      <body>
        <script src="/cdn-cgi/challenge-platform/h/g/orchestrate/chl_page/v1"></script>
      </body>
    </html>
    """
    assert looks_like_access_interstitial(html_text) is True


def test_detects_attention_required_cloudflare_page() -> None:
    html_text = """
    <html>
      <head><title>Attention Required! | Cloudflare</title></head>
      <body>Cloudflare Ray ID: 123</body>
    </html>
    """
    assert looks_like_access_interstitial(html_text) is True


def test_regular_article_page_is_not_interstitial() -> None:
    html_text = """
    <html>
      <head><title>Introducing OpenAI Frontier</title></head>
      <body><main><h1>Introducing OpenAI Frontier</h1><p>Article body.</p></main></body>
    </html>
    """
    assert looks_like_access_interstitial(html_text) is False
