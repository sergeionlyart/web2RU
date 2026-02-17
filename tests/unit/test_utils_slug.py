from __future__ import annotations

from pathlib import Path

from web2ru.utils import ensure_unique_slug


def test_ensure_unique_slug_uses_counter_when_hash_slug_exists(tmp_path: Path) -> None:
    slug = "example"
    (tmp_path / slug).mkdir()
    first = ensure_unique_slug(tmp_path, slug, "https://example.com")
    (tmp_path / first).mkdir()
    second = ensure_unique_slug(tmp_path, slug, "https://example.com")
    assert first != second
    assert second.startswith(first)
