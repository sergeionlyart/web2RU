from __future__ import annotations

from web2ru.surf.server import _navigation_error_details


def test_navigation_error_details_for_unsupported_scheme() -> None:
    status, title, body = _navigation_error_details(
        error=ValueError("unsupported URL scheme: ftp")
    )
    assert status == 400
    assert title == "Unsupported Link"
    assert "http/https" in body


def test_navigation_error_details_for_max_pages_limit() -> None:
    status, title, body = _navigation_error_details(
        error=RuntimeError("surf max pages reached: 30")
    )
    assert status == 429
    assert title == "Page Limit Reached"
    assert "--surf-max-pages" in body


def test_navigation_error_details_for_interstitial_block() -> None:
    status, title, body = _navigation_error_details(
        error=RuntimeError(
            "Access interstitial detected during online render; target content is blocked by anti-bot challenge. (attempts=3)"
        )
    )
    assert status == 502
    assert title == "Source Access Blocked"
    assert "anti-bot challenge" in body


def test_navigation_error_details_for_medium_auth_required() -> None:
    status, title, body = _navigation_error_details(
        error=RuntimeError(
            "Medium authentication required. Run this command and complete login: "
            "web2ru 'https://medium.com/' --auth-capture on --headful"
        )
    )
    assert status == 401
    assert title == "Medium Login Required"
    assert "--auth-capture on --headful" in body
