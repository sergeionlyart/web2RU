from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from web2ru.surf.router import canonicalize_source_url


@dataclass(slots=True)
class ManifestPage:
    source_url: str
    page_key: str
    status: str
    output_dir: str | None
    error: str | None
    updated_at: str

    def as_dict(self) -> dict[str, str | None]:
        return {
            "source_url": self.source_url,
            "page_key": self.page_key,
            "status": self.status,
            "output_dir": self.output_dir,
            "error": self.error,
            "updated_at": self.updated_at,
        }


class SurfManifest:
    def __init__(self, *, path: Path, origin_url: str) -> None:
        self.path = path
        self.origin_url = canonicalize_source_url(origin_url)
        self._pages_by_url: dict[str, ManifestPage] = {}
        self._pages_by_key: dict[str, ManifestPage] = {}

    @classmethod
    def load_or_create(cls, *, path: Path, origin_url: str) -> SurfManifest:
        manifest = cls(path=path, origin_url=origin_url)
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                loaded_origin = payload.get("origin_url")
                if isinstance(loaded_origin, str) and loaded_origin.strip():
                    manifest.origin_url = canonicalize_source_url(loaded_origin)
                pages = payload.get("pages")
                if isinstance(pages, list):
                    for item in pages:
                        if not isinstance(item, dict):
                            continue
                        page = _manifest_page_from_dict(item)
                        if page is None:
                            continue
                        manifest._pages_by_url[page.source_url] = page
                        manifest._pages_by_key[page.page_key] = page
        manifest.save()
        return manifest

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "origin_url": self.origin_url,
            "pages": [page.as_dict() for page in self._pages_by_url.values()],
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_by_url(self, source_url: str) -> ManifestPage | None:
        return self._pages_by_url.get(canonicalize_source_url(source_url))

    def get_by_page_key(self, page_key: str) -> ManifestPage | None:
        return self._pages_by_key.get(page_key)

    def upsert(self, page: ManifestPage) -> None:
        canonical = canonicalize_source_url(page.source_url)
        page.source_url = canonical
        self._pages_by_url[canonical] = page
        self._pages_by_key[page.page_key] = page
        self.save()

    def ready_pages_count(self) -> int:
        return sum(1 for page in self._pages_by_url.values() if page.status == "ready")

    def mark_running(self, *, source_url: str, page_key: str) -> ManifestPage:
        page = ManifestPage(
            source_url=canonicalize_source_url(source_url),
            page_key=page_key,
            status="running",
            output_dir=None,
            error=None,
            updated_at=_utc_now(),
        )
        self.upsert(page)
        return page

    def mark_ready(self, *, source_url: str, page_key: str, output_dir: str) -> ManifestPage:
        page = ManifestPage(
            source_url=canonicalize_source_url(source_url),
            page_key=page_key,
            status="ready",
            output_dir=output_dir,
            error=None,
            updated_at=_utc_now(),
        )
        self.upsert(page)
        return page

    def mark_failed(self, *, source_url: str, page_key: str, error: str) -> ManifestPage:
        page = ManifestPage(
            source_url=canonicalize_source_url(source_url),
            page_key=page_key,
            status="failed",
            output_dir=None,
            error=error,
            updated_at=_utc_now(),
        )
        self.upsert(page)
        return page


def _manifest_page_from_dict(item: dict[str, object]) -> ManifestPage | None:
    source_url = item.get("source_url")
    page_key = item.get("page_key")
    status = item.get("status")
    updated_at = item.get("updated_at")
    if not isinstance(source_url, str):
        return None
    if not isinstance(page_key, str):
        return None
    if not isinstance(status, str):
        return None
    if not isinstance(updated_at, str):
        return None
    output_dir_raw = item.get("output_dir")
    error_raw = item.get("error")
    output_dir = output_dir_raw if isinstance(output_dir_raw, str) else None
    error = error_raw if isinstance(error_raw, str) else None
    return ManifestPage(
        source_url=canonicalize_source_url(source_url),
        page_key=page_key,
        status=status,
        output_dir=output_dir,
        error=error,
        updated_at=updated_at,
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
