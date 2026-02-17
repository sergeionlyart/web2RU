from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import urlparse

_SAFE_SEGMENT_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def slugify_url(url: str, max_length: int = 80) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "page").lower()
    path = parsed.path.strip("/")
    path = path if path else "index"
    combined = f"{host}-{path}".replace("/", "-")
    combined = _SAFE_SEGMENT_RE.sub("-", combined).strip("-")
    if not combined:
        combined = "snapshot"
    if len(combined) <= max_length:
        return combined
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:10]
    return f"{combined[: max_length - 11]}-{digest}".strip("-")


def ensure_unique_slug(output_root: Path, slug: str, source_url: str) -> str:
    out = output_root / slug
    if not out.exists():
        return slug
    digest = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:8]
    base = f"{slug}-{digest}"
    candidate = base
    index = 2
    while (output_root / candidate).exists():
        candidate = f"{base}-{index}"
        index += 1
    return candidate


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def clamp_non_negative(value: int) -> int:
    return value if value >= 0 else 0
