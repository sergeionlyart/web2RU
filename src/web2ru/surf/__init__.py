from __future__ import annotations

from web2ru.surf.router import (
    SURF_GO_PATH,
    SURF_PAGE_PREFIX,
    build_go_route,
    build_page_route,
    canonicalize_source_url,
    page_key_for_url,
    same_origin,
)
from web2ru.surf.server import serve_surf_session
from web2ru.surf.session import SurfPageResult, SurfSession

__all__ = [
    "SURF_GO_PATH",
    "SURF_PAGE_PREFIX",
    "SurfPageResult",
    "SurfSession",
    "build_go_route",
    "build_page_route",
    "canonicalize_source_url",
    "page_key_for_url",
    "same_origin",
    "serve_surf_session",
]
