from __future__ import annotations

import html
import mimetypes
import webbrowser
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

from web2ru.surf.router import SURF_GO_PATH, SURF_PAGE_PREFIX, build_page_route, parse_go_query
from web2ru.surf.session import SurfSession


class SurfHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], session: SurfSession) -> None:
        super().__init__(server_address, SurfRequestHandler)
        self.session = session


class SurfRequestHandler(BaseHTTPRequestHandler):
    server: SurfHTTPServer

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        path = parsed.path
        if path in {"", "/", "/index.html"}:
            self._redirect_to_start_page()
            return
        if path == SURF_GO_PATH:
            self._handle_go_route(query=parsed.query)
            return
        if path.startswith(f"{SURF_PAGE_PREFIX}/"):
            self._handle_page_route(path=path)
            return
        self._send_html(404, "Not Found", "Unknown route.")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def _redirect_to_start_page(self) -> None:
        try:
            page = self.server.session.ensure_page_for_navigation(self.server.session.origin_url)
        except Exception as exc:
            self._send_html(500, "Initialization error", str(exc))
            return
        self._redirect(build_page_route(page.page_key))

    def _handle_go_route(self, *, query: str) -> None:
        target_url = parse_go_query(query)
        if target_url is None:
            self._send_html(400, "Bad request", "Missing `url` query parameter.")
            return
        try:
            page = self.server.session.ensure_page_for_navigation(target_url)
        except Exception as exc:
            self._send_navigation_error(target_url=target_url, error=exc)
            return
        fragment = page.fragment if page.fragment else None
        self._redirect(build_page_route(page.page_key, fragment=fragment))

    def _handle_page_route(self, *, path: str) -> None:
        prefix = f"{SURF_PAGE_PREFIX}/"
        tail = path[len(prefix) :]
        if not tail:
            self._send_html(404, "Not Found", "Missing page key.")
            return
        parts = tail.split("/", 1)
        page_key = parts[0]
        rel_path = "index.html"
        if len(parts) > 1 and parts[1]:
            rel_path = parts[1]

        page_dir = self.server.session.get_page_output_dir(page_key)
        if page_dir is None:
            source_url = self.server.session.get_source_url_by_page_key(page_key)
            if source_url is None:
                self._send_html(404, "Not Found", "Unknown page key.")
                return
            try:
                self.server.session.ensure_page_for_navigation(source_url)
            except Exception as exc:
                self._send_navigation_error(target_url=source_url, error=exc)
                return
            page_dir = self.server.session.get_page_output_dir(page_key)
            if page_dir is None:
                self._send_html(500, "Internal error", "Page marked ready but output missing.")
                return

        self._serve_file(root=page_dir, rel_path=rel_path)

    def _serve_file(self, *, root: Path, rel_path: str) -> None:
        candidate = (root / rel_path).resolve()
        root_resolved = root.resolve()
        if root_resolved not in candidate.parents and candidate != root_resolved:
            self._send_html(403, "Forbidden", "Invalid path.")
            return
        if candidate.is_dir():
            candidate = (candidate / "index.html").resolve()
        if not candidate.exists() or not candidate.is_file():
            self._send_html(404, "Not Found", "File not found.")
            return

        mime, _ = mimetypes.guess_type(str(candidate))
        content_type = mime or "application/octet-stream"
        data = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_navigation_error(self, *, target_url: str, error: Exception) -> None:
        status, title, body = _navigation_error_details(error=error)
        source_link = ""
        parsed = urlsplit(target_url)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            escaped_url = html.escape(target_url, quote=True)
            source_link = (
                "<p><a href='"
                + escaped_url
                + "' target='_blank' rel='noopener noreferrer'>Open original page</a></p>"
            )
        self._send_html(status, title, body, extra_html=source_link)

    def _send_html(self, status: int, title: str, body: str, *, extra_html: str = "") -> None:
        html = (
            "<html><head><meta charset='utf-8'><title>"
            + html_escape(title)
            + "</title></head><body><h1>"
            + html_escape(title)
            + "</h1><p>"
            + html_escape(body)
            + "</p></body></html>"
        )
        if extra_html:
            html = html.replace("</body></html>", extra_html + "</body></html>")
        data = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, location: str) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()


def serve_surf_session(*, session: SurfSession, port: int, open_in_browser: bool) -> None:
    with SurfHTTPServer(("127.0.0.1", port), session) as httpd:
        selected_port = _extract_server_port(httpd)
        url = f"http://127.0.0.1:{selected_port}/"
        print(f"Surf serving at {url}")
        if open_in_browser:
            webbrowser.open(url)
        print("Press Ctrl+C to stop server.")
        with suppress(KeyboardInterrupt):
            httpd.serve_forever()


def _extract_server_port(httpd: ThreadingHTTPServer) -> int:
    address = cast(tuple[str, int], httpd.server_address)
    return int(address[1])


def _navigation_error_details(*, error: Exception) -> tuple[int, str, str]:
    message = str(error).strip()
    lowered = message.lower()
    if isinstance(error, ValueError):
        if "unsupported url scheme" in lowered:
            return (
                400,
                "Unsupported Link",
                "This link cannot be translated. Only http/https URLs are supported.",
            )
        if "cross-origin navigation is disabled" in lowered:
            return (
                400,
                "External Link Blocked",
                "Cross-origin navigation is disabled. Restart with --surf-same-origin-only off.",
            )
        return 400, "Bad Link", message or "The target link is invalid."
    if isinstance(error, RuntimeError):
        if message.startswith("surf max pages reached:"):
            return (
                429,
                "Page Limit Reached",
                "Session page limit reached. Increase --surf-max-pages and retry.",
            )
        if "medium authentication required" in lowered:
            return (
                401,
                "Medium Login Required",
                message,
            )
        if "access interstitial detected" in lowered or "anti-bot challenge" in lowered:
            return (
                502,
                "Source Access Blocked",
                "The target site returned an anti-bot challenge. Translation is unavailable right now.",
            )
    return 500, "Translation Error", message or "Failed to translate the target page."


def html_escape(value: str) -> str:
    return html.escape(value, quote=False)
