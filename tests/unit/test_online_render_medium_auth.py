from __future__ import annotations

import pytest

from web2ru.pipeline.online_render import _maybe_raise_medium_auth_required


def test_medium_auth_required_for_signin_path() -> None:
    with pytest.raises(RuntimeError) as exc:
        _maybe_raise_medium_auth_required(
            final_url="https://medium.com/m/signin",
            html_text="<html><head><title>Sign in</title></head><body></body></html>",
        )
    assert "Medium authentication required" in str(exc.value)
    assert "--auth-capture on --headful" in str(exc.value)


def test_medium_auth_not_required_for_regular_article_html() -> None:
    _maybe_raise_medium_auth_required(
        final_url="https://medium.com/@author/some-article",
        html_text="<html><body><article><h1>Title</h1></article></body></html>",
    )


def test_medium_auth_check_ignored_for_non_medium_hosts() -> None:
    _maybe_raise_medium_auth_required(
        final_url="https://example.com/page",
        html_text="<html><body>log in to medium</body></html>",
    )
